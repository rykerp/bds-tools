from .geometry import Geometry

class GeometryLibrary:
    def __init__(self, asset, json_asset):
        self.geometries = {}
        for geom in json_asset.get("geometry_library", []):
                g = Geometry(asset, geom)
                self.geometries[g.id] = g

    def find(self, id):
        return self.geometries.get(id, None)
