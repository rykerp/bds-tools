from .util import rotation_to_blender
from .util import coords_to_blender, parse_xyz_coords


class Node:
    def __init__(self, asset, json_node):
        self.asset = asset

        self.id = json_node["id"]
        self.name = json_node.get("name", self.id)
        self.label = json_node.get("label", self.name)
        self.type = "node"
        self.parent = None
        self._rotation_order = "XYZ"
        self.inherits_scale = True  # except for a bone with a bone parent
        self._center_point = [0, 0, 0]
        self._end_point = [0, 0, 0]
        self._orientation = [0, 0, 0]
        self._rotation = [0, 0, 0]
        self._translation = [0, 0, 0]
        self._scale = [1, 1, 1]
        self.general_scale = 1

        self.parse(json_node)

    @property
    def rotation_order(self):
        return {
            "XYZ": "XZY",
            "XZY": "XYZ",
            "YXZ": "ZXY",
            "YZX": "ZYX",
            "ZXY": "YXZ",
            "ZYX": "YZX"
        }[self._rotation_order]

    @property
    def center_point(self):
        return coords_to_blender(self._center_point)

    @property
    def end_point(self):
        return coords_to_blender(self._end_point)

    @property
    def orientation(self):
        return rotation_to_blender(self._orientation)

    @property
    def rotation(self):
        return rotation_to_blender(self._rotation)

    @property
    def translation(self):
        return coords_to_blender(self._translation)

    @property
    def scale(self):
        return [self._scale[0], self._scale[2], self._scale[1]]

    def parse(self, json_node):
        self.type = json_node.get("type", self.type)
        self.parent = json_node.get("parent", self.parent)
        self._rotation_order = json_node.get("rotation_order", self._rotation_order)
        self.inherits_scale = json_node.get("inherits_scale", self.inherits_scale)
        self._center_point = parse_xyz_coords(json_node.get("center_point", {}), self._center_point)
        self._end_point = parse_xyz_coords(json_node.get("end_point", {}), self._end_point)
        self._orientation = parse_xyz_coords(json_node.get("orientation", {}), self._orientation)
        self._rotation = parse_xyz_coords(json_node.get("rotation", {}), self._rotation)
        self._translation = parse_xyz_coords(json_node.get("translation", {}), self._translation)
        self._scale = parse_xyz_coords(json_node.get("scale", {}), self._scale)
        self.general_scale = json_node.get("general_scale", {}).get("value", self.general_scale)
        self.general_scale = json_node.get("general_scale", {}).get("current_value", self.general_scale)
