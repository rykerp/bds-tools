from .util import vertices_to_blender


class Geometry:
    def __init__(self, asset, geom):
        self.asset = asset
        self.id = geom["id"]
        self.poly_groups = [{"name": name, "vertices": set()} for name in geom["polygon_groups"]["values"]]
        self.mat_groups = [{"name": name, "vertices": set(), "faces": set()} for name in geom["polygon_material_groups"]["values"]]
        self.vertices = vertices_to_blender(geom["vertices"]["values"])
        self.default_uv_set = self.load_default_uv_set(geom)
        self.faces = list()
        for polygon in geom["polylist"]["values"]:
            (polygroup_index, material_index, v) = (polygon[0], polygon[1], polygon[2:])
            self.faces.append(v)
            self.poly_groups[polygroup_index]["vertices"].update(v)
            self.mat_groups[material_index]["vertices"].update(v)
            self.mat_groups[material_index]["faces"].update([len(self.faces) - 1])

    def load_default_uv_set(self, geom):
        return self.asset.find_uv_set(geom["default_uv_set"])

    def mat_group_to_faces(self, mat_group):
        for mg in self.mat_groups:
            if mg["name"] == mat_group:
                return mg["faces"]
        return []
