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
    location = bl_obj.pose.bones[bone_name].location
    a = x if x is not None else location[0]
    b = -z if z is not None else location[2]
    c = y if y is not None else location[1]
    bl_obj.pose.bones[bone_name].location = (a, b, c)


def apply_rotation(bl_obj, bone, x, y, z):
    if bone not in bl_obj.data.edit_bones:
        return

    sign = 1 if bl_obj.data.edit_bones[bone].bdst_sign[0] == "+" else -1
    mode = bl_obj.data.edit_bones[bone].bdst_sign[1]
    #mode = bl_obj.pose.bones[bone].rotation_mode[0]
    a = None
    b = "D"
    c = "d"

    if mode == "X":
        if sign == -1:
            z *= -1
            x *= -1
        a = z
        b = x
        c = y
        #b_info.rotation_order = swap_rot(rot_order, {"X": "Y", "Y": "X", "Z": "Z"})
    if mode == "Y":
        if sign == -1:
            z *= -1
            x *= -1
        a = x
        b = y
        c = z
        #b_info.rotation_order = swap_rot(rot_order, {"X": "X", "Y": "Y", "Z": "Z"})
    if mode == "Z":
        if sign == -1:
            y *= -1
            z *= -1
        a = x
        b = y
        c = z
        #b_info.rotation_order = swap_rot(rot_order, {"X": "X", "Y": "Z", "Z": "Y"})

    if a is None or a == "":
        a = bl_obj.pose.bones[bone].rotation_euler[0]
    if b is None or b == "":
        b = bl_obj.pose.bones[bone].rotation_euler[1]
    if c is None or c == "":
        c = bl_obj.pose.bones[bone].rotation_euler[2]

    bl_obj.pose.bones[bone].rotation_euler = (radians(a), radians(b), radians(c))


def load_pose(filepath, context):
    start_time = time.time()

    asset = types.Asset(filepath)
    bl_obj = context.active_object
    bpy.ops.object.mode_set(mode='EDIT')

    animations = asset.scene.animations
    for bone, rot in asset.scene.bone_rot.items():
        #if bone not in ["lShldr", "lForeArm"]:
        #    continue
        if bone not in bl_obj.pose.bones:
            log.warn("bone %s not found!" % bone)
            continue

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
