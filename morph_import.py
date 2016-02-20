import fnmatch
import logging
import os
import time
from collections import OrderedDict
from functools import partial

import bpy
from mathutils import Vector

from bpy.props import BoolProperty, StringProperty, FloatProperty

from .types.util import Uri
from . import types
from . import pose_import
from . import armature

log = logging.getLogger(__name__)


def load_morph(filepath, context):
    start_time = time.time()

    files = [filepath]
    if not os.path.isfile(filepath):
        files.clear()
        for f in os.listdir(filepath):
            abs_file = os.path.join(filepath, f)
            if os.path.isfile(abs_file) and f.endswith(".dsf"):
                files.append(abs_file)

    for file in files:
        asset = types.Asset(file)

        bl_obj = context.active_object
        create_morphs(bl_obj, asset)

    end_time = time.time()
    elapsed_time = end_time - start_time
    log.debug("imported %d morphs in %.3f seconds" % (len(files), elapsed_time))


def load_all_morphs(dir, bl_obj):
    start_time = time.time()

    if not os.path.exists(dir):
        return

    files = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, "*.dsf"):
            if "CTRLRIG" not in filename:  # no idea what the purpose of CTRLRIG morphs is
                log.debug("appending morph filename " + filename)
                files.append(os.path.join(root, filename))

    for file in files:
        asset = types.Asset(file)
        log.debug("asset.id " + asset.asset_id)
        create_morphs(bl_obj, asset)

    end_time = time.time()
    elapsed_time = end_time - start_time
    log.debug("imported %d morphs in %.3f seconds" % (len(files), elapsed_time))


def create_morphs(bl_obj, asset):
    for key, modifier in asset.modifier_library.modifiers.items():
        log.debug("modifier %s type=%s" % (modifier.id, modifier.type))
        if modifier.type == "morph":
            if modifier.morph is not None:
                create_shapekey(bl_obj, modifier)
            bl_morph = bl_obj.bdst_morphs.add()
            bl_morph.name = modifier.id
            bl_morph.visible = (not modifier.channel) or modifier.channel.visible
            for formula in modifier.formulas:
                # ignore formulas with unknown operations
                valid = True
                for operation in formula.operations:
                    valid = valid and operation.op != "spline_tcb"
                if not valid:
                    continue

                bl_formula = bl_morph.formulas.add()
                bl_formula.output = formula.output
                bl_formula.stage = formula.stage
                for operation in formula.operations:
                    bl_operation = bl_formula.operations.add()
                    bl_operation.op = operation.op
                    bl_operation.val = operation.val if operation.val else 0.0
                    bl_operation.url = operation.url if operation.url else ""


def get_morph_value(self):
    if "value" in self:
        return self["value"]
    return 0.0


def set_morph_value(self, value):
    if "value" not in self or abs(value - self["value"]) > 0.001:
        self["value"] = value

        bl_obj = bpy.context.object
        bl_morph = self
        log.debug("setting %s to value %.3f" % (bl_morph.name, value))
        apply_morph(bl_obj, bl_morph, value, process_outputs=True)


def apply_morph(bl_obj, bl_morph, value, process_outputs=True):
    log.debug("apply morph %s %.3f %s" % (bl_morph.name, value, process_outputs))
    sk = find_shape_key(bl_obj, bl_morph.name)
    if sk:
        sk.value = value

    outputs = []
    for bl_formula in bl_morph.formulas:
        stack = []
        for bl_operation in bl_formula.operations:
            execute_operation(bl_obj, stack, bl_operation)

        output = bl_formula.output
        stage = bl_formula.stage
        value = stack.pop()
        log.debug("%s: %.3f" %(output, value))
        outputs.append(FormulaResult(output, stage, value))

    non_morph_outputs = process_morphs(bl_obj, bl_morph, outputs)
    if process_outputs:
        process_formula_outputs(bl_obj, bl_morph, non_morph_outputs)
        return []
    else:
        return non_morph_outputs


def process_morphs(bl_obj, bl_morph, outputs):
    """ Recursively process and apply all morphs, return all formulas with a non-morph output """
    non_morphs = []

    # handle morphs
    for formula_result in outputs:
        uri = Uri(formula_result.output)
        asset_id = uri.asset_id
        morph = find_morph(bl_obj, asset_id)
        if morph and morph is not bl_morph:
            # set value first to avoid endless recursion of bpy property setter
            morph["value"] = formula_result.value
            morph.value = formula_result.value
            non_morphs.extend(apply_morph(bl_obj, morph, formula_result.value, process_outputs=False))
        elif morph:  # formula references containing morph, change only shape_key
            sk = find_shape_key(bl_obj, bl_morph.name)
            if sk:
                sk.value = formula_result.value
        else:
            non_morphs.append(formula_result)

    return non_morphs


def process_formula_outputs(bl_obj, bl_morph, outputs):
    """ All morphs have already been handled by process_morphs, outputs is the final list of all properties
    that will be transformed / changed here """

    # combine formula outputs that will change the same property
    combined = {}
    for formula_result in outputs:
        target = formula_result.output
        if target in combined:
            partial_result = combined[target]
            if formula_result.stage == "sum":
                partial_result.value += formula_result.value
            else:  # assume 'mult'
                partial_result.value *= formula_result.value
        else:
            combined[target] = formula_result

    arm = None
    pose_bone_transformations = OrderedDict()
    edit_bone_transformations = OrderedDict()
    for _, formula_result in combined.items():
        uri = Uri(formula_result.output)
        asset_id = uri.asset_id
        property_path = uri.property_path

        pose_transforms = ["rotation", "translation", "scale"]
        edit_transforms = ["center_point", "end_point", "orientation"]
        is_pose = True in [property_path.startswith(pt) for pt in pose_transforms]
        is_edit = True in [property_path.startswith(pt) for pt in edit_transforms]

        if is_pose or is_edit:
            arm, pose_bone = find_pose_bone(bl_obj, asset_id)
            if arm and pose_bone:
                bone_transformations = edit_bone_transformations if is_edit else pose_bone_transformations
                if asset_id in bone_transformations:
                    bt = bone_transformations[asset_id]
                else:
                    bt = BoneTransformation(asset_id)
                    bone_transformations[asset_id] = bt

                transform = property_path.split("/")[-2]
                axis = property_path.split("/")[-1]
                bt.update(transform, axis, formula_result.value)

    if len(pose_bone_transformations) > 0:
        old_obj = bpy.context.active_object
        bpy.context.scene.objects.active = arm
        old_mode = arm.mode
        bpy.ops.object.mode_set(mode='EDIT')
        for _, pbt in pose_bone_transformations.items():
            log.debug("apply pose to %s rot=%s scale=%s translation=%s" % (pbt.bone_name, pbt.rotation, pbt.scale, pbt.translation))
            pose_import.apply_rotation(arm, pbt.bone_name, *pbt.rotation)
            pose_import.apply_scale(arm, pbt.bone_name, *pbt.scale)
            pose_import.apply_translation(arm, pbt.bone_name, *pbt.translation)
        bpy.ops.object.mode_set(mode=old_mode)
        bpy.context.scene.objects.active = old_obj

    if len(edit_bone_transformations) > 0:
        old_obj = bpy.context.active_object
        bpy.context.scene.objects.active = arm
        old_mode = arm.mode
        bpy.ops.object.mode_set(mode='EDIT')
        for _, ebt in edit_bone_transformations.items():
            log.debug("apply transform to edit bone %s cp=%s ep=%s orient=%s" % (ebt.bone_name, ebt.center_point, ebt.end_point, ebt.orientation))
            armature.transform_edit_bone(arm, ebt.bone_name, ebt.center_point, ebt.end_point, ebt.orientation)
        bpy.ops.object.mode_set(mode=old_mode)
        bpy.context.scene.objects.active = old_obj


def find_pose_bone(bl_obj, bone_name):
    armature = bl_obj
    while armature is not None and armature.type != 'ARMATURE':
        armature = bl_obj.parent
    if armature:
        return armature, armature.pose.bones.get(bone_name, None)
    return None, None


class BoneTransformation:
    def __init__(self, bone_name):
        self.bone_name = bone_name
        self.rotation = ["", "", ""]
        self.translation = [0, 0, 0]
        self.scale = [0, 0, 0]
        self.center_point = [0, 0, 0]
        self.end_point = [0, 0, 0]
        self.orientation = [0, 0, 0]

    def update(self, transform, axis, value):
        map = {
            "x": 0, "y": 1, "z": 2
        }
        if transform == "scale" and axis == "general":
            self.scale = [value, value, value]
        else:
            getattr(self, transform)[map[axis]] = value


class FormulaResult:
    def __init__(self, output, stage, value):
        self.output = output
        self.stage = stage
        self.value = value


def execute_operation(bl_obj, stack, bl_operation):
    op = bl_operation.op
    operators = {
        "push": execute_push,
        "add": partial(execute_arith, lambda a, b: a + b),
        "sub": partial(execute_arith, lambda a, b: a - b),
        "mult": partial(execute_arith, lambda a, b: a * b),
        "div": partial(execute_arith, lambda a, b: a / b)
    }
    operators[op](bl_obj, stack, bl_operation)


def execute_push(bl_obj, stack, bl_operation):
    val = bl_operation.val
    if len(bl_operation.url) > 0:
        val = resolve_url_to_val(bl_obj, bl_operation.url)
    stack.append(val)


def execute_arith(arith, bl_obj, stack, bl_operation):
    a = stack.pop()
    b = stack.pop()
    result = arith(a, b)
    stack.append(result)


def resolve_url_to_val(bl_obj, url):
    uri = Uri(url)
    asset_id = uri.asset_id
    property_path = uri.property_path

    morph = find_morph(bl_obj, asset_id)
    if morph:
        # assume property_path is always 'value'
        return morph.value

    # TODO bones, nodes
    return -1.99


def find_morph(bl_obj, morph_name):
    return bl_obj.bdst_morphs.get(morph_name, None)


def find_shape_key(bl_obj, morph_name):
    log.debug("search morph " + morph_name)
    return bl_obj.data.shape_keys.key_blocks.get(morph_name, None)


def create_shapekey(bl_obj, modifier):
    base_shape_key = get_base_shape_key(bl_obj)
    log.debug("modifier %s type=%s" % (modifier.id, modifier.type))

    shape_key_name = modifier.id
    shape_key = bl_obj.shape_key_add(shape_key_name)
    shape_key_data = shape_key.data
    shape_key_values = shape_key_data.values()
    for (delta_idx, x, y, z) in modifier.morph.vertex_deltas:
        # add the deltas to their respective shape-key coordinates.
        shape_key_values[delta_idx].co += Vector((x / 100.0, z / -100.0, y / 100.0))


def get_base_shape_key(obj):
    """get or create the base shapekey for object.
    """
    if obj.data.shape_keys is None:
        base_shape_key = obj.shape_key_add('base')
    else:
        base_shape_key = obj.data.shape_keys.reference_key
    return base_shape_key


class BlenderOperation(bpy.types.PropertyGroup):
    op = bpy.props.StringProperty(name="op")
    val = bpy.props.FloatProperty(name="val")
    url = bpy.props.StringProperty(name="url")


class BlenderFormula(bpy.types.PropertyGroup):
    output = bpy.props.StringProperty(name="output")
    operations = bpy.props.CollectionProperty(type=BlenderOperation)
    stage = bpy.props.StringProperty(name="stage", default="sum")


class BlenderMorph(bpy.types.PropertyGroup):
    formulas = bpy.props.CollectionProperty(type=BlenderFormula)
    visible = bpy.props.BoolProperty(name="visible")
    value = bpy.props.FloatProperty(name="Value", min=0.0, max=1.0, subtype='FACTOR',
                                    get=get_morph_value, set=set_morph_value)


class MorphList(bpy.types.UIList):
    # The draw_item function is called for each item of the collection that is visible in the list.
    #   data is the RNA object containing the collection,
    #   item is the current drawn item of the collection,
    #   icon is the "computed" icon for the item (as an integer, because some objects like materials or textures
    #   have custom icons ID, which are not available as enum items).
    #   active_data is the RNA object containing the active property for the collection (i.e. integer pointing to the
    #   active item of the collection).
    #   active_propname is the name of the active property (use 'getattr(active_data, active_propname)').
    #   index is index of the current item in the collection.
    #   flt_flag is the result of the filtering process for this item.
    #   Note: as index and flt_flag are optional arguments, you do not have to use/declare them here if you don't
    #         need them.
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        bl_obj = data
        bl_morph = item

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            split = layout.split(0.66, False)
            split.prop(bl_morph, "name", text="", emboss=False, icon='SHAPEKEY_DATA')
            row = split.row(align=True)
            row.prop(bl_morph, "value", text="", emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)

    def filter_items(self, context, data, propname):
        morphs = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        # Default return values.
        flt_flags = []
        flt_neworder = []

        # Filtering by name
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(self.filter_name, self.bitflag_filter_item, morphs, "name",
                                                          reverse=self.use_filter_sort_reverse)
        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(morphs)

        # Do not show invisible morphs (JCM, MCM, etc.)
        for idx, morph in enumerate(morphs):
            if not morph.visible:
                flt_flags[idx] &= ~self.bitflag_filter_item

        if self.use_filter_sort_alpha:
            flt_neworder = helper_funcs.sort_items_by_name(morphs, "name")

        return flt_flags, flt_neworder


class MorphPanel(bpy.types.Panel):
    bl_category = "BDS-Tools"
    bl_label = "Morphs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        layout = self.layout
        bl_obj = context.object
        layout.template_list("MorphList", "cust", bl_obj, "bdst_morphs", bl_obj, "bdst_active_morph_index")

        if bl_obj and bl_obj.type == 'MESH':
            active_morph = bl_obj.bdst_morphs[bl_obj.bdst_active_morph_index]
            layout.prop(active_morph, "value")


class MorphImporter(bpy.types.Operator):
    bl_label = "import morph from dson"
    bl_idname = "bdst.import_morph"

    use_filter_folder = True
    filepath = StringProperty(
            name="file path",
            description="file path for importing dsf-file.",
            maxlen=1000,
            subtype="DIR_PATH",
            default="")

    def execute(self, context):
        load_morph(self.properties.filepath, context)
        return {"FINISHED"}

    def invoke(self, context, event):
        # show file selection dialog
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def morph_import_menu(self, context):
    self.layout.operator(MorphImporter.bl_idname, text = "DSON/dsf morph (.dsf)")


def register():
    bpy.utils.register_class(MorphImporter)
    bpy.utils.register_class(MorphPanel)
    bpy.utils.register_class(BlenderOperation)
    bpy.utils.register_class(BlenderFormula)
    bpy.utils.register_class(BlenderMorph)
    bpy.utils.register_class(MorphList)

    bpy.types.INFO_MT_file_import.append(morph_import_menu)
    bpy.types.Object.bdst_morphs = bpy.props.CollectionProperty(type=BlenderMorph)
    bpy.types.Object.bdst_active_morph_index = bpy.props.IntProperty()


def unregister():
    bpy.utils.unregister_class(MorphImporter)
    bpy.utils.unregister_class(MorphPanel)
    bpy.utils.unregister_class(BlenderOperation)
    bpy.utils.unregister_class(BlenderFormula)
    bpy.utils.unregister_class(BlenderMorph)
    bpy.utils.unregister_class(MorphList)
    bpy.types.INFO_MT_file_import.remove(morph_import_menu)
