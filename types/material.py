import copy

from .util import extract

import logging

log = logging.getLogger(__name__)


class Material:
    def __init__(self, json_material):
        self.id = json_material["id"]
        self.type = json_material.get("type", "unknown")

        self.channels = {}
        self.parse_channels(json_material)

        self.extras = []
        self.parse_extra_channels(json_material)

        self.uv_set = json_material.get("uv_set", None)

    def update(self, json_material):
        # XXX: mat instance has own id but cant risk overriding it
        self.groups = json_material["groups"]
        self.geometry = json_material["geometry"]
        self.parse_channels(json_material)
        self.parse_extra_channels(json_material)
        self.uv_set = json_material.get("uv_set", self.uv_set)

    def parse_channels(self, json_material):
        std_channels = ["diffuse", "diffuse_strength", "specular", "specular_strength", "glossiness",
                        "ambient", "ambient_strength", "reflection", "reflection_strength", "refraction",
                        "refraction_strength", "ior", "bump", "bump_min", "bump_max", "displacement", "displacement_min",
                        "displacement_max", "transparency", "normal", "u_offset", "v_offset", "v_scale"]
        for std in std_channels:
            if std in json_material:
                self.channels[std] = Channel(json_material[std])

    def parse_extra_channels(self, json_material):
        for json_extra in json_material.get("extra", []):
            extra = Extra(json_extra)
            prev_extra = self.find_extra_type(extra.type)
            if not prev_extra:
                self.extras.append(extra)
            else:
                prev_extra.merge(extra)

    def find_extra_type(self, type):
        return next((e for e in self.extras if e.type == type), None)

    def find_extra_channel(self, id):
        for extra in self.extras:
            if id in extra.channels:
                return extra.channels[id]
        return None


class MaterialInstance:
    def __init__(self, asset, json_material):
        self.id = json_material["id"]
        self.url = json_material["url"]
        self.material = copy.deepcopy(asset.find_material(self.url))
        self.material.update(json_material)

    def __getattr__(self, attr):
        return getattr(self.material, attr)


class Extra:
    def __init__(self, json_extra):
        self.type = json_extra["type"]
        log.debug("extra type %s" % self.type)
        self.channels = {}
        for json_channel in json_extra.get("channels", []):
            channel = Channel(json_channel)
            log.debug("channel parsed with id %s" % channel.id)
            self.channels[channel.id] = channel

    def merge(self, other_extra):
        for chan_id, other_chan in other_extra.channels.items():
            my_chan = self.channels.get(chan_id, None)
            if my_chan:
                my_chan.merge(other_chan)
            else:
                self.channels[other_chan.id] = other_chan


class Channel:
    @property
    def current_value(self):
        if self._current_value is not None:
            return self._current_value
        return self.value

    def __init__(self, json_channel):
        chan = json_channel["channel"]
        self.id = chan["id"]
        self.type = chan["type"]
        self.label = chan.get("label", "")
        self.value = chan.get("value", None)
        self.visible = chan.get("visible", True)
        self._current_value = chan.get("current_value", None)
        self.image = chan.get("image", None)
        self.image_file = chan.get("image_file", None)
        self.group = json_channel.get("group", "")

    def merge(self, other_chan):
        if other_chan.value:
            self.value = other_chan.value
        if other_chan.current_value:
            self._current_value = other_chan._current_value
        if other_chan.image_file:
            self.image_file = other_chan.image_file

