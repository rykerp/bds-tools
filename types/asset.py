import os

import bpy
import json
import logging
import urllib.parse


log = logging.getLogger(__name__)

from .util import open_text_file
from .geometry_library import GeometryLibrary
from .material_library import MaterialLibrary
from .scene import Scene
from .uv_set_library import UvSetLibrary
from .node_library import NodeLibrary
from .modifier_library import ModifierLibrary
from .image_library import ImageLibrary


class Asset:
    def __init__(self, filepath):
        self.filepath = filepath
        self.root_path = self.find_root_path(filepath)
        reader = open_text_file(filepath)
        json_asset = json.load(reader)

        self.json_asset = json_asset
        self.asset_id = urllib.parse.unquote(json_asset["asset_info"]["id"])

        self.supporting_assets = {}
        self.uv_set_library = UvSetLibrary(self, json_asset)
        self.geometry_library = GeometryLibrary(self, json_asset)
        self.material_library = MaterialLibrary(self, json_asset)
        self.image_library = ImageLibrary(self, json_asset)
        self.node_library = NodeLibrary(self, json_asset)
        self.modifier_library = ModifierLibrary(self, json_asset)

        self.scene = Scene(self, self.json_asset)

    def find_root_path(self, filepath):
        #return filepath.split("Content")[0] + "Content"
        user_preferences = bpy.context.user_preferences
        addon_prefs = user_preferences.addons["bds-tools"].preferences
        content_root = addon_prefs.content_root
        if not os.path.exists(content_root):
            raise Exception("Content root dir does not exist. Set it in addon preferences.")
        return content_root

    def find_geometry(self, url):
        return self.internal_find_object(url, self.geometry_library)

    def find_geometry_instance(self, url):
        log.debug("searching for geometry instance " + url)
        url = urllib.parse.unquote(url)
        if url.find("#") < 0:
            raise Exception("url has no id: " + url)
        path, id = url.split("#")

        for node in self.scene.nodes:
            for geom in node.geometries:
                if geom.id == id:
                    log.debug("found it, geometry instance was already loaded")
                    return geom
        raise Exception("could not find geometry instance with url " + url)

    def find_node(self, url):
        return self.internal_find_object(url, self.node_library)

    def find_material(self, url):
        return self.internal_find_object(url, self.material_library)

    def find_uv_set(self, url):
        return self.internal_find_object(url, self.uv_set_library)

    def find_modifier(self, url):
        return self.internal_find_object(url, self.modifier_library)

    def find_image(self, url):
        return self.internal_find_object(url, self.image_library)

    def internal_find_object(self, url, collection):
        log.debug("searching for object " + url)
        url = urllib.parse.unquote(url)
        if url.find("#") < 0:
            raise Exception("url has no id: " + url)
        path, id = url.split("#")

        if len(path) == 0:
            object = collection.find(id)
            if object is not None:
                log.debug("found it, object was already loaded")
                return object
            else:
                raise Exception("local id but asset could not be found " + url)

        if path not in self.supporting_assets:
            log.debug("loading support asset")
            support_asset = Asset(self.root_path + path)
            self.supporting_assets[path] = support_asset

        # hmm, id's have to be unique within one file. merge find over all libraries?
        object = None
        if collection is self.uv_set_library:
            object = self.supporting_assets[path].uv_set_library.find(id)
        elif collection is self.geometry_library:
            object = self.supporting_assets[path].geometry_library.find(id)
        elif collection is self.material_library:
            object = self.supporting_assets[path].material_library.find(id)
        elif collection is self.node_library:
            object = self.supporting_assets[path].node_library.find(id)
        elif collection is self.modifier_library:
            object = self.supporting_assets[path].modifier_library.find(id)
        elif collection is self.image_library:
            object = self.supporting_assets[path].image_library.find(id)

        if object is not None:
            log.debug("found object in support asset")
            return object
        else:
            #if (collection is self.uv_set_library):
            #   for k, v in self.uv_set_library.uv_sets.items():
            #        log.debug("uv: " + k)
            raise Exception("could not find object with url " + url)


