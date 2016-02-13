from .uv_set import UvSet


class UvSetLibrary:
    def __init__(self, asset, json_asset):
        self.uv_sets = {}
        self.parse(json_asset)

    def parse(self, json_asset):
        for json_uv_set in json_asset.get("uv_set_library", []):
            uv_set = UvSet(json_uv_set)
            self.uv_sets[uv_set.id] = uv_set

    def find(self, id):
        return self.uv_sets.get(id, None)

