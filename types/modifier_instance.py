import copy

from .material import Channel


class ModifierInstance:
    def __init__(self, asset, json_modifier):
        self.id = json_modifier["id"]
        self.url = json_modifier["url"]
        self.parent = json_modifier.get("parent", None)

        self.channel = None
        if "channel" in json_modifier:
            self.channel = Channel(json_modifier)

        self.modifier = copy.copy(asset.find_modifier(self.url))

    def __getattr__(self, attr):
        return getattr(self.modifier, attr)
