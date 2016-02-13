import logging

from .material import Material

log = logging.getLogger(__name__)


class MaterialLibrary:
    def __init__(self, asset, json_asset):
        self.asset = asset
        self.json_asset = json_asset
        self.materials = {}
        for json_material in json_asset.get("material_library", []):
            self.parse_material(json_material)
        for url, mat in self.materials.items():
            log.debug("added material %s" % mat.id)

    def parse_material(self, json_material):
        mat = Material(json_material)
        self.materials[mat.id] = mat

    def find(self, id):
        return self.materials.get(id, None)
