import fnmatch
import logging
import os
import time
from math import radians

import bpy
from mathutils import Vector
from mathutils import Euler
from mathutils import Matrix

from bpy.props import BoolProperty, StringProperty
from . import types

log = logging.getLogger(__name__)


class PoseImporter(bpy.types.Operator):
    bl_label = "import pose from dson"
    bl_idname = "bdst.import_pose"

    use_filter_folder = True
    filepath = StringProperty(
            name="file path",
            description="file path for importing duf-file.",
            maxlen=1000,
            subtype="DIR_PATH",
            default="")

    def execute(self, context):
        load_pose(self.properties.filepath, context)
        return {"FINISHED"}

    def invoke(self, context, event):
        # show file selection dialog
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def apply_scale(bl_obj, bone_name, x, y, z):
    scale = bl_obj.pose.bones[bone_name].scale
    a = scale[0] + x if x is not None else scale[0]
    b = scale[2] + z if z is not None else scale[2]
    c = scale[1] + y if y is not None else scale[1]
    bl_obj.pose.bones[bone_name].scale = (a, b, c)


def apply_translation(bl_obj, bone_name, x, y, z):
    edit_bone, pose_bone = find_edit_and_pose_bone(bl_obj, bone_name)
    if edit_bone is None or pose_bone is None:
        log.error("bone not found %s" % bone_name)
        return

    a, b, c = transform_bone_orientation(edit_bone, x, y, z)

    location = pose_bone.location
    if a is None or a == "":
        a = location[0]
    if b is None or b == "":
        b = location[2]
    if c is None or c == "":
        c = location[1]

    bl_obj.pose.bones[bone_name].location = (a/100, b/100, c/100)


def apply_rotation(bl_obj, bone_name, x, y, z):
    edit_bone, pose_bone = find_edit_and_pose_bone(bl_obj, bone_name)
    if edit_bone is None or pose_bone is None:
        log.error("bone not found %s" % bone_name)
        return

    a, b, c = transform_bone_orientation(edit_bone, x, y, z)

    if a is None or a == "":
        a = pose_bone.rotation_euler[0]
    if b is None or b == "":
        b = pose_bone.rotation_euler[1]
    if c is None or c == "":
        c = pose_bone.rotation_euler[2]

    bl_obj.pose.bones[bone_name].rotation_euler = (radians(a), radians(b), radians(c))


def transform_bone_orientation(edit_bone, x, y, z):
    sign = 1 if edit_bone.bdst_sign[0] == "+" else -1
    mode = edit_bone.bdst_sign[1]
    a = None
    b = None
    c = None

    if mode == "X":
        if sign == -1:
            z *= -1
            x *= -1
        a = z
        b = x
        c = y
    if mode == "Y":
        if sign == -1:
            x *= -1
        a = x
        b = z
        c = y
    if mode == "Z":
        if sign == -1:
            y *= -1
            z *= -1
        a = x
        b = y
        c = z
    return a, b, c


def find_edit_and_pose_bone(bl_armature, bone_name):
    if bone_name not in bl_armature.data.edit_bones:
        bone = find_bone_by_instance_id(bone_name, bl_armature.data.edit_bones)
        if bone is None:
            return None, None
        bone_name = bone.name
    return bl_armature.data.edit_bones[bone_name], bl_armature.pose.bones[bone_name]


def find_bone_by_instance_id(instance_id, edit_bones):
    for bone in edit_bones:
        if bone.bdst_instance_id == instance_id:
            return bone
    return None


def load_pose(filepath, context):
    start_time = time.time()

    asset = types.Asset(filepath)
    bl_obj = context.active_object
    bpy.ops.object.mode_set(mode='EDIT')

    animations = asset.scene.animations
    for bone, rot in asset.scene.bone_rot.items():
        #if bone not in ["lShldr", "lForeArm"]:
        #    continue
        #if bone not in bl_obj.pose.bones:
        #    log.warn("bone %s not found!" % bone)
        #    continue

        x = rot["x"]
        y = rot["y"]
        z = rot["z"]
        log.debug("%s: x=%.3f y=%.3f z=%.3f" % (bone, x, y, z))
        apply_rotation(bl_obj, bone, x, y, z)

    bpy.ops.object.mode_set(mode='OBJECT')

    end_time = time.time()
    elapsed_time = end_time - start_time
    log.debug("imported %d animations in %.3f seconds" % (len(animations), elapsed_time))


def pose_import_menu(self, context):
    self.layout.operator(PoseImporter.bl_idname, text = "DSON/dsf pose (.duf)")


def register():
    bpy.utils.register_class(PoseImporter)
    bpy.types.INFO_MT_file_import.append(pose_import_menu)


def unregister():
    bpy.utils.unregister_class(PoseImporter)
    bpy.types.INFO_MT_file_import.remove(pose_import_menu)
