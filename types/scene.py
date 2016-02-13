from collections import defaultdict, OrderedDict

from .node_instance import NodeInstance
from .modifier_instance import ModifierInstance
from .material import MaterialInstance


class Scene:
    def __init__(self, asset, json_asset):
        self.asset = asset
        self.json_asset = json_asset

        self.nodes = []
        self.parse_nodes()

        self.materials = []
        self.parse_materials()

        self.modifiers = []
        self.parse_modifiers()

        #self.bone_rot = defaultdict(lambda: {"x": 0, "y": 0, "z": 0})
        self.bone_rot = OrderedDict()
        self.animations = []
        self.parse_animations()

    def parse_nodes(self):
        for json_node in self.json_asset.get("scene", {}).get("nodes", []):
            self.parse_node(json_node)

    def parse_node(self, json_node):
        self.nodes.append(NodeInstance(self.asset, json_node))

    def parse_materials(self):
        for json_material in self.json_asset.get("scene", {}).get("materials", []):
            self.parse_material(json_material)

    def parse_material(self, json_material):
        self.materials.append(MaterialInstance(self.asset, json_material))

    def parse_modifiers(self):
        for json_modifier in self.json_asset.get("scene", {}).get("modifiers", []):
            self.parse_modifier(json_modifier)

    def parse_modifier(self, json_modifier):
        self.modifiers.append(ModifierInstance(self.asset, json_modifier))

    def parse_animations(self):
        for json_anim in self.json_asset.get("scene", {}).get("animations", []):
            self.parse_animation(json_anim)

    def parse_animation(self, json_anim):
        self.animations.append(Animation(self.bone_rot, json_anim))


class Animation:
    def __init__(self, bone_rot, json_anim):
        self.url = json_anim["url"]
        self.keys = json_anim["keys"]

        self.bone = None
        self.rotation_x = 0
        self.rotation_y = 0
        self.rotation_z = 0

        try:
            self.bone = self.url.split("/")[3].split(":")[0]

            if self.bone not in bone_rot:
                bone_rot[self.bone] = {"x": 0, "y": 0, "z": 0}
            if "rotation/x/value" in self.url:
                bone_rot[self.bone]["x"] = self.keys[0][1]
            if "rotation/y/value" in self.url:
                bone_rot[self.bone]["y"] = self.keys[0][1]
            if "rotation/z/value" in self.url:
                bone_rot[self.bone]["z"] = self.keys[0][1]
        except Exception:
            pass


