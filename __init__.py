if "bpy" in locals():
    import importlib
    importlib.reload(asset_import)
    importlib.reload(morph_import)
    importlib.reload(pose_import)
    importlib.reload(armature)
    importlib.reload(types)
    importlib.reload(types.asset)
    importlib.reload(types.geometry)
    importlib.reload(types.geometry_library)
    importlib.reload(types.image)
    importlib.reload(types.image_library)
    importlib.reload(types.material)
    importlib.reload(types.material_library)
    importlib.reload(types.modifier)
    importlib.reload(types.modifier_instance)
    importlib.reload(types.modifier_library)
    importlib.reload(types.node)
    importlib.reload(types.node_instance)
    importlib.reload(types.node_library)
    importlib.reload(types.scene)
    importlib.reload(types.util)
    importlib.reload(types.uv_set)
    importlib.reload(types.uv_set_library)
else:
    from . import asset_import
    from . import types
    from . import morph_import
    from . import pose_import
    from . import armature

import bpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty
import logging

logging.basicConfig(level=logging.DEBUG)

bl_info = {
    "name": "BDS-Tools",
    "description": "Import meshes, materials etc. from DSON files",
    "author": "Ryker",
    "version": (0, 9),
    "blender": (2, 76, 0),
    "location": "https://github.com/rykerp/bds-tools",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "",
    "category": "Import-Export"
}

class BdstAddonPreferences(AddonPreferences):
    bl_idname = __name__

    content_root = StringProperty(
            name="Content Root Directory",
            default="C:\\Users\\Public\\Documents\\My DAZ 3D Library",
            subtype='DIR_PATH'
            )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Content Root is where your data, Runtime, Environment, People, etc. folders are located")
        layout.prop(self, "content_root")


def register():
    bpy.types.EditBone.bdst_sign = bpy.props.StringProperty(name="bone orientation sign")
    bpy.types.EditBone.bdst_center_point = bpy.props.FloatVectorProperty(name="bone center point")
    bpy.types.EditBone.bdst_end_point = bpy.props.FloatVectorProperty(name="bone end point")
    bpy.types.EditBone.bdst_orientation = bpy.props.FloatVectorProperty(name="bone orientation")

    bpy.utils.register_class(BdstAddonPreferences)
    asset_import.register()
    morph_import.register()
    pose_import.register()


def unregister():
    bpy.utils.unregister_class(BdstAddonPreferences)
    asset_import.unregister()
    morph_import.unregister()
    pose_import.unregister()
