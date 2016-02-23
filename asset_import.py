import collections
import os
import re
import time
from collections import namedtuple, defaultdict, OrderedDict
from math import radians, degrees
import urllib.parse

import bpy
import bmesh
import logging
import mathutils

from bpy.props import BoolProperty, StringProperty

from . import pose_import
from .morph_import import load_all_morphs
from .types.util import fix_broken_path
from . import types
from . import armature

log = logging.getLogger(__name__)

class AssetImporter(bpy.types.Operator):
    bl_label = "import asset from dson"
    bl_idname = "bdst.import_asset"

    filepath = StringProperty(
            name="file path",
            description="file path for importing dsf-file.",
            maxlen=1000,
            default="")

    def execute(self, context):
        # import the file here
        log.debug("file to load %s" % self.properties.filepath)
        load_asset(self.properties.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        # show file selection dialog
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def asset_import_menu(self, context):
    self.layout.operator(AssetImporter.bl_idname, text = "DSON/duf asset (.duf)")


def find_bl_object_for_geom_id(blender_objects, geometry_id):
    if geometry_id is None:
        return None

    geometry_id = urllib.parse.unquote(geometry_id)
    if geometry_id.startswith("#"):
        geometry_id = geometry_id[1:]

    pattern = re.compile("%s.\d\d\d" % geometry_id)
    for obj in blender_objects:
        log.debug("searching geom %s -> checking %s" % (geometry_id, obj.name))
        if obj.type == 'MESH' and (obj.data.name == geometry_id or pattern.match(obj.data.name)):
            log.debug("match geom %s -> %s" % (geometry_id, obj.data.name))
            return obj
    return None


def find_bl_object_for_node_id(blender_objects, node_id):
    if node_id is None:
        return None

    node_id = urllib.parse.unquote(node_id)
    if node_id.startswith("#"):
        node_id = node_id[1:]

    pattern = re.compile("%s.\d\d\d" % node_id)
    for obj in blender_objects:
        log.debug("searching object %s -> checking %s" % (node_id, obj.name))
        if obj.name == node_id or pattern.match(obj.name):
            log.debug("match obj %s -> %s" % (node_id, obj.name))
            return obj
    return None


def find_root_object(bl_object):
    tmp = bl_object
    while tmp.parent is not None:
        tmp = tmp.parent
    return tmp


def find_all_children(blender_objects, bl_parent):
    children = find_direct_children(blender_objects, bl_parent)
    if len(children) == 0:
        return []

    all_children = children
    for child in children:
        all_children.extend(find_all_children(blender_objects, child))
    return all_children


def find_direct_children(blender_objects, bl_parent):
    return [child for child in blender_objects if child.parent == bl_parent]


def load_asset(filepath):
    start_time = time.time()

    # secure active object here, as it might get changed later
    active_object = bpy.context.active_object
    active_is_selected = len(bpy.context.selected_objects) > 0

    asset = types.Asset(filepath)

    blender_objects = []
    bones = OrderedDict()  # uses node_instance id as key
    bone_node_ids = []     # uses node id
    armature_children = []
    for node in asset.scene.nodes:
        bl_obj = None
        for geom in node.geometries:  # XXX: might be better to create one bl_object from multiple geometries here
            bl_obj = create_object_from_geometry(node, geom)
            blender_objects.append(bl_obj)

            dir_name = os.path.dirname(geom.asset.filepath)
            morphs_path = os.path.join(dir_name, "Morphs")
            load_all_morphs(morphs_path, bl_obj)

        if node.type == "node" and len(node.geometries) == 0:
            # this is a group node, use an emtpy
            bl_obj = create_empty(node)
            blender_objects.append(bl_obj)

        def is_figure_but_not_clothing(node): return node.type == "figure" and node.parent is None
        def is_standalone_clothing(node): return node.type == "figure" and "@selection" in node.parent
        if is_figure_but_not_clothing(node) or is_standalone_clothing(node):
            bones[node.id] = node
            if bl_obj is not None:
                armature_children.append(bl_obj)
        if node.type == "bone" and node.node.id not in bone_node_ids:
            # don't add bone if its node id was already added to bone_node_ids as it is most
            # likely a bone from a piece of clothing and might have a different transform which might
            # override the transform of the parent bone
            bones[node.id] = node
            bone_node_ids.append(node.node.id)

    # slow, but needed to calculate sharp edges
    bl_obj_to_ek = prepare_edges_faces_dict(blender_objects)

    for material in asset.scene.materials:
        geometry_id = material.geometry
        geometry = asset.find_geometry_instance(geometry_id)
        bl_obj = find_bl_object_for_geom_id(blender_objects, geometry_id)
        uv_map_name = find_uv_map_for_material(asset, material, bl_obj)
        bl_mat = create_cycles_material(asset, bl_obj, material, uv_map_name)
        assign_material_to_groups(bl_obj, bl_mat, bl_obj_to_ek, material, geometry)

    if active_object and active_is_selected and active_object.type == 'ARMATURE' and len(armature_children) > 0:
        bl_armature = active_object
    else:
        _, bl_armature = armature.create_armature(list(bones.values()))
    if bl_armature is not None and len(armature_children) > 0:
        armature_children[0].parent = bl_armature

    # setup parent relationships (so children will get affected by transforms later)
    geometry_nodes = [node for node in asset.scene.nodes if node.type in ["node", "figure"]]
    for node in geometry_nodes:
        parent = node.parent
        if parent and "@selection" in parent:
            continue
        if node.conform_target and not node.parent:
            # sometimes parent is not set but conform_target is
            parent = node.conform_target

        bl_parent = find_bl_object_for_geom_id(blender_objects, parent)
        if bl_parent is None:
            bl_parent = find_bl_object_for_node_id(blender_objects, parent)
        if bl_parent is None and bl_armature is not None and parent is not None:
            bl_parent = bl_armature
        if bl_parent is not None and bl_parent is not bl_armature:
            bl_obj = find_bl_object_for_node_id(blender_objects, node.id)
            bl_obj.parent = bl_parent
            # important!: set parent but keep transformation
            bl_obj.matrix_parent_inverse = bl_parent.matrix_world.inverted()
        if bl_parent is not None and bl_parent is bl_armature:
            bl_obj = find_bl_object_for_node_id(blender_objects, node.id)
            set_bone_as_relative_parent(bl_obj, bl_armature, bones[parent[1:]])

    # do necessary transforms
    for node in geometry_nodes:
        bl_obj = find_bl_object_for_node_id(blender_objects, node.id)

        if bl_armature is not None and bl_obj.parent == bl_armature and node.type != "node":
            # if the object is a direct child of an armature we have to transform the armature object instead
            # BUT: props like weapons seem to be of type "node" and need their own rotation, maybe check
            # for bone-parenting instead
            bl_obj = bl_armature
        elif bl_armature is not None and find_root_object(bl_obj) == bl_armature and node.conform_target is not None:
            # do not transform descendants of armature if conform_target is set
            continue

        log.debug("obj %s trans=%s rot=%s" % (bl_obj.name, node.translation, node.rotation))
        tr = mathutils.Vector(node.translation)
        bl_obj.location = bl_obj.location + tr
        rot = node.rotation
        bl_obj.rotation_euler = rot
        bl_obj.scale = node.scale
        bl_obj.scale *= node.general_scale

    for modifier in asset.scene.modifiers:
        if modifier.type == "skin":
            bl_obj = find_bl_object_for_geom_id(blender_objects, modifier.parent)
            if bl_obj is None:
                bl_obj = find_bl_object_for_node_id(blender_objects, modifier.parent)
            for joint in modifier.skin.joints.values():
                create_weight_group(bl_obj, joint, bones)
        elif modifier.type == "morph" and modifier.parent and modifier.channel:
            bl_obj = find_bl_object_for_node_id(blender_objects, modifier.parent)
            if bl_obj is None:
                continue
            bl_morph = bl_obj.bdst_morphs.get(modifier.modifier.id, None)
            if bl_morph:
                bpy.context.scene.objects.active = bl_obj
                bl_morph.value = modifier.channel.current_value

    if bl_armature is not None:
        children = find_all_children(blender_objects, bl_armature)
        for child in children:
            modifier = child.modifiers.new("Armature", type='ARMATURE')
            modifier.object = bl_armature
            modifier.use_deform_preserve_volume = True
        transform_bones(list(bones.values()), bl_armature)

    end_time = time.time()
    elapsed_time = end_time - start_time
    log.info("imported %d objects in %.3f seconds" % (len(blender_objects), elapsed_time))


def create_weight_group(obj, joint, bones):
    log.debug("create_weight_group obj=%s joint=%s" % (obj.name, joint.id))
    name = joint.id
    if name not in bones:
        # TODO: some clothes have bones that are not in the parent figure.
        # TODO: find these bones and create them in the parent figure's armature.
        # just ignore them right now
        log.error("could not find bone %s" % name)
        return
    node = bones[name]

    bone_head = node.center_point
    bone_tail = node.end_point

    calc_weights = []
    if joint.local_weights is not None:
        # find longitudinal axis of the bone and take the other two into consideration
        consider = []
        x_delta = abs(bone_head[0] - bone_tail[0])
        y_delta = abs(bone_head[1] - bone_tail[1])
        z_delta = abs(bone_head[2] - bone_tail[2])
        max_delta = max(x_delta, y_delta, z_delta)
        if x_delta < max_delta:
            consider.append("x")
        if y_delta < max_delta:
            consider.append("y")
        if z_delta < max_delta:
            consider.append("z")

        # create deques sorted in descending order
        weights = [collections.deque(joint.local_weights[letter]) for letter in consider if letter in joint.local_weights]
        for w in weights:
            w.reverse()

        target = []
        if len(weights) == 1:
            calc_weights = weights[0]
        elif len(weights) > 1:
            merge_weights(weights[0], weights[1], target)
            calc_weights = target
        if len(weights) > 2:
            # this happens mostly with zero length bones
            calc_weights = []
            merge_weights(target, weights[2], calc_weights)
    elif joint.node_weights is not None:
        calc_weights = joint.node_weights

    vg_name = node.node.id
    if vg_name in obj.vertex_groups:
        vg = obj.vertex_groups[vg_name]
        obj.vertex_groups.remove(vg)
    vg = obj.vertex_groups.new(name=vg_name)
    for vw in calc_weights:
        if vw[1] >= 0.001:
            vg.add([vw[0]], vw[1], "REPLACE")


def merge_weights(first, second, target):
    # merge the two local_weight groups and calculate arithmetic mean for vertices that are present in both groups
    while len(first) > 0 and len(second) > 0:
        a = first.pop()
        b = second.pop()
        if a[0] == b[0]:
            target.append([a[0], (a[1] + b[1]) / 2.0])
        elif a[0] < b[0]:
            target.append(a)
            second.append(b)
        else:
            target.append(b)
            first.append(a)
    while len(first) > 0:
        a = first.pop()
        target.append(a)
    while len(second) > 0:
        b = second.pop()
        target.append(b)


def prepare_edges_faces_dict(blender_objects):
    # for finding edges and faces by edge_key
    result = {}
    for bl_obj in blender_objects:
        if bl_obj.type != 'MESH':
            continue

        result[bl_obj.name] = {}

        e_to_f = defaultdict(lambda: [])
        result[bl_obj.name]["e_to_f"] = e_to_f
        for i, p in enumerate(bl_obj.data.polygons):
            for ek in p.edge_keys:
                e_to_f[ek].append(i)

        result[bl_obj.name]["e_to_e"] = {ek: bl_obj.data.edges[i] for i, ek in enumerate(bl_obj.data.edge_keys)}
    return result


def assign_material_to_groups(bl_obj, bl_mat, bl_obj_to_ek, material, geometry):
    groups = material.groups
    material_idx = find_material_index(bl_obj, bl_mat)
    for group in groups:
        smooth_chan = material.find_extra_channel("Smooth On")
        use_smooth = smooth_chan.current_value if smooth_chan and smooth_chan.current_value is not None else False
        smooth_angle_chan = material.find_extra_channel("Smooth Angle")
        smooth_angle = smooth_angle_chan.current_value if smooth_angle_chan and smooth_angle_chan.current_value is not None else -1

        faces = geometry.mat_group_to_faces(group)

        for face_idx in faces:
            # XXX: this check is necessary because we might have deleted some invalid faces
            # XXX: this also means that some materials might be assigned to the wrong faces...
            if face_idx < len(bl_obj.data.polygons):
                poly = bl_obj.data.polygons[face_idx]
                poly.material_index = material_idx
                poly.use_smooth = use_smooth
                if smooth_angle >= 0:
                    handle_smooth_angle(bl_obj, bl_obj_to_ek, poly, smooth_angle)


def handle_smooth_angle(bl_obj, bl_obj_to_ek, poly, smooth_angle):
    for ek in poly.edge_keys:
        polys = bl_obj_to_ek[bl_obj.name]["e_to_f"][ek]
        if len(polys) == 2:
            # log.debug("len polys is 2")
            normal0 = mathutils.Vector(bl_obj.data.polygons[polys[0]].normal)
            normal1 = mathutils.Vector(bl_obj.data.polygons[polys[1]].normal)
            try:
                angle = degrees(normal0.angle(normal1))
            except:
                angle = -1
            # log.debug("************** angle: %.3f" % angle)
            if angle >= smooth_angle:
                edge = bl_obj_to_ek[bl_obj.name]["e_to_e"][ek]
                # log.debug("setting edge to sharp")
                edge.use_edge_sharp = True
                if "EdgeSplit" not in bl_obj.modifiers:
                    modifier = bl_obj.modifiers.new("EdgeSplit", type='EDGE_SPLIT')
                    modifier.use_edge_angle = False
                    modifier.use_edge_sharp = True


def find_material_index(bl_obj, bl_mat):
    index = 0
    for i, mat_slot in enumerate(bl_obj.material_slots):
        if mat_slot.material is not None and mat_slot.name == bl_mat.name:
            index = i
    return index


def load_node_group(node_group_name):
    if node_group_name in bpy.data.node_groups:
        return bpy.data.node_groups[node_group_name]

    filepath = os.path.dirname(__file__) + "/blend/material.blend"
    link = False  # append

    # append node group from .blend file
    with bpy.data.libraries.load(filepath, link=link) as (data_src, data_dst):
        data_dst.node_groups = [node_group_name]

    return bpy.data.node_groups[node_group_name]


def load_image(path):
    if not os.path.exists(path):
        path = fix_broken_path(path)

    for img in bpy.data.images:
        if img.filepath == path:
            return img

    return bpy.data.images.load(path)


def channel_color_to_input(channel_name, input_name, channels, nodes, asset, links, group):
    if channel_name not in channels:
        return

    chan = channels[channel_name]
    val = chan.value
    if chan.current_value:
        val = chan.current_value
    if val:
        group.inputs[input_name].default_value = val + [1]  # + alpha
    channel_load_image(chan, input_name, nodes, asset, links, group)


def channel_float_to_input(channel_name, input_name, channels, nodes, asset, links, group):
    if channel_name not in channels:
        return

    chan = channels[channel_name]
    val = chan.value
    if chan.current_value:
        val = chan.current_value
    if val:
        group.inputs[input_name].default_value = val
    channel_load_image(chan, input_name, nodes, asset, links, group)


def channel_load_image(chan, input_name, nodes, asset, links, group):
    image_path = None
    if chan.image:
        image = asset.find_image(chan.image)
        image_path = urllib.parse.unquote(image.map_url)
    if chan.image_file:
        image_path = urllib.parse.unquote(chan.image_file)
    if image_path:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.location = (-600, 400)
        path = asset.root_path + image_path
        tex_node.image = load_image(path)
        links.new(tex_node.outputs["Color"], group.inputs[input_name])


def create_cycles_material(asset, bl_obj, material, uv_map_name):
    bl_mat = bpy.data.materials.new(material.id)
    bl_obj.data.materials.append(bl_mat)
    bl_mat.use_nodes = True

    tree = bl_mat.node_tree

    nodes = tree.nodes
    links = tree.links

    # delete default nodes
    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (300, 300)

    group = nodes.new("ShaderNodeGroup")
    group.node_tree = load_node_group("MatGroup")
    links.new(group.outputs[0], output_node.inputs["Surface"])

    channel_color_to_input("diffuse", "diffuse", material.channels, nodes, asset, links, group)
    channel_float_to_input("diffuse_strength", "diffuse_strength", material.channels, nodes, asset, links, group)
    channel_color_to_input("specular", "specular", material.channels, nodes, asset, links, group)
    channel_float_to_input("specular_strength", "specular_strength", material.channels, nodes, asset, links, group)
    channel_float_to_input("glossiness", "glossiness", material.channels, nodes, asset, links, group)
    channel_color_to_input("ambient", "ambient", material.channels, nodes, asset, links, group)
    channel_float_to_input("ambient_strength", "ambient_strength", material.channels, nodes, asset, links, group)
    channel_color_to_input("reflection", "reflection", material.channels, nodes, asset, links, group)
    channel_float_to_input("reflection_strength", "reflection_strength", material.channels, nodes, asset, links, group)
    channel_color_to_input("refraction", "refraction", material.channels, nodes, asset, links, group)
    channel_float_to_input("refraction_strength", "refraction_strength", material.channels, nodes, asset, links, group)
    channel_float_to_input("ior", "ior", material.channels, nodes, asset, links, group)
    channel_float_to_input("bump", "bump", material.channels, nodes, asset, links, group)
    channel_float_to_input("bump_min", "bump_min", material.channels, nodes, asset, links, group)
    channel_float_to_input("bump_max", "bump_max", material.channels, nodes, asset, links, group)
    channel_float_to_input("displacement", "displacement", material.channels, nodes, asset, links, group)
    channel_float_to_input("displacement_min", "displacement_min", material.channels, nodes, asset, links, group)
    channel_float_to_input("displacement_max", "displacement_max", material.channels, nodes, asset, links, group)
    channel_float_to_input("transparency", "transparency", material.channels, nodes, asset, links, group)
    channel_color_to_input("normal", "normal", material.channels, nodes, asset, links, group)

    extra = material.find_extra_type("studio_material_channels")
    if extra:
        channels = extra.channels
        channel_float_to_input("Bump Strength", "bump", channels, nodes, asset, links, group)
        channel_float_to_input("Bump Minimum", "bump_min", material.channels, nodes, asset, links, group)
        channel_float_to_input("Bump Maximum", "bump_max", material.channels, nodes, asset, links, group)
        channel_float_to_input("Displacement Strength", "displacement", channels, nodes, asset, links, group)
        channel_color_to_input("Specular Color", "specular", channels, nodes, asset, links, group)

        # "Bump Active"
        #channel_color_to_input("Specular2 Color", "???", channels, nodes, asset, links, group)
        #channel_color_to_input("Subsurface Color", "???", channels, nodes, asset, links, group)
        #channel_color_to_input("Translucency Color", "???", channels, nodes, asset, links, group)

    texture_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']
    if len(texture_nodes) > 0:
        uv_map_node = nodes.new("ShaderNodeUVMap")
        uv_map_node.location = (-800, 400)
        uv_map_node.uv_map = uv_map_name
        for tex_node in texture_nodes:
            links.new(uv_map_node.outputs[0], tex_node.inputs["Vector"])

    return bl_mat


def create_object_from_geometry(node, geom):
    bmesh_mesh = bmesh.new()
    for v in geom.vertices:
        bmesh_mesh.verts.new(v)

    bmesh_mesh.verts.ensure_lookup_table()

    for (face_idx, face_vis) in enumerate(geom.faces):
        face_verts = [bmesh_mesh.verts[vi] for vi in face_vis]

        # ensure enough and unique vertices per face
        if len(face_verts) > 2 and len(face_verts) == len(set(face_verts)):
            try:
                bmesh_mesh.faces.new(face_verts)
            except ValueError as e:
                log.error("while trying to create face: %s" % e)
        else:
            # this is bad because it changes face indexes
            log.debug("error in " + geom.id)
            log.debug([vi for vi in face_vis])

    obj = create_blender_mesh_object(node.id, geom.id, bmesh_mesh)
    set_origin_point(obj, node.center_point)
    create_vertex_groups(obj, geom.poly_groups)
    create_vertex_groups(obj, geom.mat_groups)
    create_uv_map(obj, geom.default_uv_set)
    return obj


def set_origin_point(bl_obj, center_point):
    log.debug("setting origin point %s %s" % (bl_obj.name, center_point))
    old_obj = bpy.context.active_object
    for item in bpy.context.selectable_objects:
        item.select = False

    bpy.context.scene.objects.active = bl_obj
    bl_obj.select = True

    old_mode = bl_obj.mode
    old_cursor_pos = bpy.context.scene.cursor_location.copy()
    bpy.context.scene.cursor_location = center_point
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.context.scene.cursor_location = old_cursor_pos
    bpy.ops.object.mode_set(mode=old_mode)
    bpy.context.scene.objects.active = old_obj
    for item in bpy.context.selectable_objects:
        item.select = False


def create_vertex_groups(obj, groups):
    for group in groups:
        vg = obj.vertex_groups.new(name=group["name"])
        weight = 1.0
        for vi in group["vertices"]:
            vg.add([vi], weight, "REPLACE")


def find_uv_map_for_material(asset, material, bl_obj):
    uv_set = asset.find_uv_set(material.uv_set)
    if uv_set and uv_set.id in bl_obj.data.uv_layers:
        return bl_obj.data.uv_layers[uv_set.id].name
    elif uv_set:
        create_uv_map(bl_obj, uv_set)
        return uv_set.id
    else:
        return bl_obj.data.uv_layers[0].name


def create_uv_map(bl_obj, uv_set):
    if uv_set is None:
        return

    bl_mesh = bl_obj.data
    bl_uv_tex = bl_mesh.uv_textures.new(name=uv_set.id)
    bl_uv_lay = bl_mesh.uv_layers[-1]
    uvoff = 0
    for bl_polygon in bl_mesh.polygons:
        uvs = uv_set.get_uvs(bl_polygon.index, bl_polygon.vertices)
        for uv_rel_idx in range(len(bl_polygon.vertices)):
            uv_pair = uvs[uv_rel_idx]
            uv_abs_idx = uvoff + uv_rel_idx
            bl_uv_lay.data[uv_abs_idx].uv = uv_pair
        uvoff += len(bl_polygon.vertices)


def create_blender_mesh_object(obj_name, mesh_name, bmesh_mesh):
    me = bpy.data.meshes.new(mesh_name)
    ob = bpy.data.objects.new(obj_name, me)
    bmesh_mesh.to_mesh(me)
    bmesh_mesh.free()
    scn = bpy.context.scene
    scn.objects.link(ob)
    me.update()
    return ob


def create_empty(node):
    empty = bpy.data.objects.new(node.id, None)
    empty.empty_draw_type = 'PLAIN_AXES'
    scn = bpy.context.scene
    scn.objects.link(empty)
    scn.update()
    return empty


def transform_bones(bones, bl_armature):
    old_obj = bpy.context.active_object
    bpy.context.scene.objects.active = bl_armature
    old_mode = bl_armature.mode
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in bones:
        bone_id = bone.node.id
        log.debug("apply pose to %s %s" % (bone_id, bone._rotation))
        pose_import.apply_rotation(bl_armature, bone_id, *bone._rotation)
    bpy.ops.object.mode_set(mode=old_mode)
    bpy.context.scene.objects.active = old_obj
    old_obj.select = True


def set_bone_as_relative_parent(bl_obj, bl_armature, bone_node):
    old_obj = bpy.context.active_object
    for item in bpy.context.selectable_objects:
        item.select = False
    bl_obj.select = True
    bl_armature.select = True
    bpy.context.scene.objects.active = bl_armature
    bl_armature.data.bones.active = bl_armature.data.bones[bone_node.node.id]
    bpy.ops.object.parent_set(type='BONE_RELATIVE')
    for item in bpy.context.selectable_objects:
        item.select = False
    bpy.context.scene.objects.active = old_obj
    old_obj.select = True


def register():
    bpy.utils.register_class(AssetImporter)
    bpy.types.INFO_MT_file_import.append(asset_import_menu)


def unregister():
    bpy.utils.unregister_class(AssetImporter)
    bpy.types.INFO_MT_file_import.remove(asset_import_menu)

