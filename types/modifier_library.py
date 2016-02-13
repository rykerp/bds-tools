from .modifier import Modifier

class ModifierLibrary:
    def __init__(self, asset, json_asset):
        self.asset = asset
        self.modifiers = {}
        for json_modifier in json_asset.get("modifier_library", []):
            modifier = Modifier(json_modifier)
            self.modifiers[modifier.id] = modifier

    def find(self, id):
        return self.modifiers.get(id, None)