import copy


class NodeInstance:
    def __init__(self, asset, json_node):
        self.asset = asset
        self.json_node = json_node

        self.id = json_node["id"]
        self.url = json_node["url"]
        self.name = json_node["name"]
        self.label = json_node["label"]
        self.conform_target = json_node.get("conform_target", None)

        self.geometries = []
        self.parse_geometries()

        self.node = copy.copy(asset.find_node(self.url))
        self.node.parse(json_node)

    def __getattr__(self, attr):
        return getattr(self.node, attr)

    def parse_geometries(self):
        for json_geometry in self.json_node.get("geometries", []):
            self.parse_geometry(json_geometry)

    def parse_geometry(self, json_geometry):
        # maybe we need a wrapper for Geometry from GeometryLibrary, e.g. GeometryReference or GeometryLink
        # ignore additional information for now
        url = json_geometry["url"]
        geometry = self.asset.find_geometry(url)

        # make a copy because the instance id might be different
        geometry_instance = copy.copy(geometry)
        geometry_instance.id = json_geometry.get("id", geometry.id)
        self.geometries.append(geometry_instance)



