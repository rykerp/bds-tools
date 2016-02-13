# contains code from https://github.com/millighost/dsf-utils
from math import radians, degrees

import bpy
import logging
import mathutils

from .types.util import coords_to_blender, rotation_to_blender

log = logging.getLogger(__name__)


class armature(object):
    """proxy object for an armature defined from a dsf file.
     provides essentially this functionality:
     - can get bones by name.
     - can identify roots.
    """

    def __init__(self, bones):
        """initialize the armature object with the json data of the node-library
           entry of the figures dsf data.
        """
        self.bone_dic = dict()
        for node in bones:
            # node is a node entry which corresponds more or less to a bone
            # in blender.
            #dsf_bone = bone(node, self)
            self.bone_dic[node.id] = node

    def get_bone(self, name):
        """get a bone by its name.
        """
        return self.bone_dic[name]

    def get_children(self, parent):
        """return all bones that are children of the bone named parent.
           returns roots for parent = None.
        """
        if parent is not None:
            parent = "#%s" % parent
        log.info("retrieve children of %s", parent)
        for (name, bone) in self.bone_dic.items():
            if bone.parent == parent:
                yield bone
        return


class bone_info(object):
    """store data on a created bone or bones.
     this is for the case when a single input bone would result in multiple
     blender bones to be created.
    """
    def __init__ (self, bone = None, bname = None):
        """create a new entry for the given blender bone name bname.
           bone is the armature bone that lead to creation of this entry.
           bname is the name of the blender bone (which is also used as a key).
        """
        assert (bone)
        assert (bname)
        self.bone = bone
        self.bname = bname
        self.roots = []
        self.leaf = None
        self.axes = []
        self.rotation_order = "XZY"


class bbone_map(dict):
    """stores mapping from a blender bone to an armature bone.
       attributes per mapping include:
       bone - a link to the armature bone
       roots - names of the blender bone that is to be used as a child for other
         blender bones connecting to the armature bone.
       leaf - name of the blender bone that is to be used as a parent for other
         blender bones connecting to the armature bone.
       axes - list of bone axis names that this bone represents.
    """

    def __init__(self, *arg, **kwarg):
        """initialize an empty bone map.
        """
        super(bbone_map, self).__init__(*arg, **kwarg)

    def get_leaf(self, id):
        """get the blender bone that represents the tail of the bones
           that were created for the bone with the id.
        """
        for b_info in self.values():
            if b_info.bone.id == id:
                return b_info.leaf
        return None


def create_armature(bones):
    if len(bones) == 0:
        return {}, None

    bone = bones[0]
    # assume bone.type == "figure":
    scene = bpy.context.scene
    name = "rig-%s" % bone.id
    armdat = bpy.data.armatures.new(name=name)
    armobj = bpy.data.objects.new(name=name, object_data=armdat)
    scene.objects.link(armobj)
    scene.objects.active = armobj
    armdat.show_axes = False
    armobj.show_x_ray = True
    armdat.draw_type = 'STICK'

    si_arm = armature(bones)

    bpy.ops.object.mode_set(mode='EDIT')
    bone_map = insert_bones(si_arm, armobj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    configure_bones(si_arm, bone_map, armobj)

    armobj.select = True
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    return bone_map, armobj


def insert_bones(si_arm, armdat):
    """traverse the bones of the armature in preorder (parent before
       children) and insert them into the armature data.
       Returns a mapping of the names of the inserted bones to their definition.
    """
    bone_mapping = bbone_map()
    # the parent queue holds bone_info-objects whose children still
    # need to get created.
    parent_queue = [None]
    while len(parent_queue) > 0:
        parent = parent_queue.pop()
        log.info("inserting children of %s", parent.id if parent else None)
        if parent is not None:
            ##### debugging ##############################################################################
            c = parent.center_point
            log.debug("center_point x=%.3f y=%.3f z=%.3f" % (c[0], c[1], c[2]))
            e = parent.end_point
            log.debug("   end_point x=%.3f y=%.3f z=%.3f" % (e[0], e[1], e[2]))
            o = parent.orientation
            log.debug(" orientation x=%.3f y=%.3f z=%.3f" % (degrees(o[0]), degrees(o[1]), degrees(o[2])))
            ##### debugging ##############################################################################

            # the parent is a b-info object and the b-infos end-attribute contains
            # the blender-bone to which children need to get linked to.
            children = list(si_arm.get_children(parent.id))
            parent_bname = bone_mapping.get_leaf(parent.id)
            parent_bbone = armdat.edit_bones[parent_bname]
        else:
            children = list(si_arm.get_children(None))
            parent_bbone = None
        for child in children:
            # create the bbones representing the child. This returns a list
            # of b-info records.
            b_infos = insert_bone(child, armdat)
            # link all blender bones to the parent
            for b_info in b_infos:
                # a blender bone might have multiple roots. assign the parent
                # to each of them.
                for bname in b_info.roots:
                    bbone_start = armdat.edit_bones[bname]
                    bbone_start.parent = parent_bbone
                bone_mapping[b_info.bname] = b_info
            parent_queue.append(child)
    return bone_mapping


def insert_bone (si_bone, armdat):
    """insert the bone object into the armature data armdat and returns
     a bone_info object created for this bone.
     created bones are name 'def-<bodypart>.<axes>'
     si_bone must provide these attributes:
     orientation, origin - basic position data of the bone used to create
       the transformation of the bone in armature-space.
    """

    #bname = "CTRL-%s" % (si_bone.id)
    bname = si_bone.id
    b_info = bone_info(bone=si_bone, bname=bname)
    b_bone = armdat.edit_bones.new(name=bname)
    orient = si_bone.orientation
    b_bone.use_deform = True

    center_point = si_bone.center_point
    end_point = si_bone.end_point
    if center_point == end_point:
        end_point = (end_point[0], end_point[1], end_point[2] + 0.3)

    len = (mathutils.Vector(center_point) - mathutils.Vector(end_point)).length
    b_bone.head = (0,0,0)
    rot_order = si_bone.rotation_order
    if si_bone.rotation_order[0] == "X":
        sign = 1 if center_point[0] < end_point[0] else -1
        b_bone.bdst_sign = "+X" if sign == 1 else "-X"
        b_info.rotation_order = swap_rot(rot_order, {"X": "Y", "Y": "X", "Z": "Z"})
        b_bone.tail = (sign * len, 0, 0)
    elif si_bone.rotation_order[0] == "Y":
        sign = 1 if center_point[1] < end_point[1] else -1
        b_bone.bdst_sign = "+Y" if sign == 1 else "-Y"
        b_info.rotation_order = swap_rot(rot_order, {"X": "X", "Y": "Y", "Z": "Z"})
        b_bone.tail = (0, sign * len, 0)
    else:
        sign = 1 if center_point[2] < end_point[2] else -1
        b_bone.bdst_sign = "+Z" if sign == 1 else "-Z"
        b_info.rotation_order = swap_rot(rot_order, {"X": "X", "Y": "Z", "Z": "Y"})
        b_bone.tail = (0, 0, sign * len)
    b_bone.roll = 0

    rot = mathutils.Euler(((orient[0]), (-orient[1]), (orient[2])), "XZY").to_matrix().to_4x4()
    b_bone.transform(rot)
    b_bone.translate(mathutils.Vector(center_point))

    b_bone.bdst_center_point = center_point
    b_bone.bdst_end_point = end_point
    b_bone.bdst_orientation = orient

    b_info.roots.append(bname)
    b_info.leaf = bname
    return [b_info]


def transform_edit_bone(bl_armature, bone_name, center_point, end_point, orientation):
    b_bone = bl_armature.data.edit_bones[bone_name]

    center_point = [
        b_bone.bdst_center_point[0] + coords_to_blender(center_point)[0],
        b_bone.bdst_center_point[1] + coords_to_blender(center_point)[1],
        b_bone.bdst_center_point[2] + coords_to_blender(center_point)[2]
    ]
    end_point = [
        b_bone.bdst_end_point[0] + coords_to_blender(end_point)[0],
        b_bone.bdst_end_point[1] + coords_to_blender(end_point)[1],
        b_bone.bdst_end_point[2] + coords_to_blender(end_point)[2]
    ]
    orientation = [
         b_bone.bdst_orientation[0] + rotation_to_blender(orientation)[0],
         b_bone.bdst_orientation[1] + rotation_to_blender(orientation)[1],
         b_bone.bdst_orientation[2] + rotation_to_blender(orientation)[2]
    ]

    if center_point == end_point:
        end_point = (end_point[0], end_point[1], end_point[2] + 0.3)

    len = (mathutils.Vector(center_point) - mathutils.Vector(end_point)).length
    b_bone.head = (0, 0, 0)
    if b_bone.bdst_sign in ["+X", "-X"]:
        sign = 1 if b_bone.bdst_sign == "+X" else -1
        b_bone.tail = (sign * len, 0, 0)
    elif b_bone.bdst_sign in ["+Y", "-Y"]:
        sign = 1 if b_bone.bdst_sign == "+Y" else -1
        b_bone.tail = (0, sign * len, 0)
    else:
        sign = 1 if b_bone.bdst_sign == "+Z" else -1
        b_bone.tail = (0, 0, sign * len)
    b_bone.roll = 0

    rot = mathutils.Euler(((orientation[0]), (-orientation[1]), (orientation[2])), "XZY").to_matrix().to_4x4()
    b_bone.transform(rot)
    b_bone.translate(mathutils.Vector(center_point))


def swap_rot(rotation_order, replace):
    result = ""
    for axis in rotation_order:
        result += replace[axis]
    return result


def configure_bones(armdat, bone_mapping, armobj):
    """perform final fixups on the created bones.
    """
    pose_bones = armobj.pose.bones
    for (bname, b_info) in bone_mapping.items():
        bbone = pose_bones[bname]
        bbone.rotation_mode = b_info.rotation_order