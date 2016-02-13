import codecs
import gzip
import os
from math import radians
import urllib.parse


def fix_broken_path(path):
    """
    many asset file paths assume a case insensitive file system, try to fix here
    :param path:
    :return:
    """
    path_components = []
    head = path
    while True:
        head, tail = os.path.split(head)
        if tail != "":
            path_components.append(tail)
        else:
            if head != "":
                path_components.append(head)
            path_components.reverse()
            break

    check = path_components[0]
    for pc in path_components[1:]:
        cand = os.path.join(check, pc)
        if not os.path.exists(cand):
            corrected = [f for f in os.listdir(check) if f.lower() == pc.lower()]
            if len(corrected) > 0:
                cand = os.path.join(check, corrected[0])
        check = cand

    return check


def open_text_file(filename, encoding = 'latin1'):
    """open a binary file and return a readable handle.
     check for compressed files and open with decompression.
    """
    if not os.path.exists(filename):
        filename = fix_broken_path(filename)

    first_bytes = open(filename, 'rb').read(2)
    if first_bytes == b'\x1f\x8b':
        # looks like a gzipped file.
        ifh = gzip.open (filename, 'rb')
    else:
        ifh = open(filename, 'rb')
    return codecs.getreader(encoding)(ifh)


def extract(json_data, key, default):
    try:
        key_parts = key.split("/")
        if len(key_parts) == 1:
            return json_data.get(key, default)
        else:
            sub_data = json_data.get(key_parts[0], default)
            return extract(sub_data, "/".join(key_parts[1:]), default)
    except Exception:
        return default


def parse_xyz_coords(json_float_array, default):
    result = default.copy()
    map = {"x": 0, "y": 1, "z": 2}
    for ch_float in json_float_array:
        val = None
        val = ch_float.get("value", val)
        val = ch_float.get("current_value", val)
        id = None
        id = ch_float.get("id", id)
        if id is not None and val is not None:
            result[map[id]] = val
    return result


def vertices_to_blender(vertices):
    return [coords_to_blender(c) for c in vertices]


def coords_to_blender(coords):
    return [
        coords[0] / 100.0,
        coords[2] / -100.0,
        coords[1] / 100.0,
    ]


def rotation_to_blender(rotation):
    return [
        radians(rotation[0]),
        radians(rotation[2]),
        radians(rotation[1])
    ]


class Uri:
    def __init__(self, uri_string):
        self.scheme = "id"  # 'id or 'name', default is 'id'
        self.node_path = ""
        self.file_path = ""
        self.asset_id = ""
        self.property_path = ""
        self.parse(uri_string)

    def parse(self, str):
        index = self.parse_scheme(str)
        index = self.parse_node_path(str, index)
        index = self.parse_file_path(str, index)
        index = self.parse_asset_id(str, index)
        index = self.parse_property_path(str, index)
        self.decode_components()

    def parse_scheme(self, str):
        index = 0
        if str.startswith("id://"):
            self.scheme = "id"
            index += len("id://")
        elif str.startswith("name://"):
            self.scheme = "name"
            index += len("name://")
        if index == 0 and "://" in str:
            raise ValueError("unknown uri scheme: " + str)
        return index

    def parse_node_path(self, str, index):
        if ":" in str[index:]:
            to = str.index(":")
            self.node_path = str[index:to]
            index += len(self.node_path) + 1
        return index

    def parse_file_path(self, str, index):
        if "#" in str[index:]:
            to = str.index("#")
            self.file_path = str[index:to]
            index += len(self.file_path) + 1
        else:
            self.file_path = str[index:]
            index += len(self.file_path)
        return index

    def parse_asset_id(self, str, index):
        if index >= len(str):
            return index
        if "?" in str[index:]:
            to = str.index("?")
            self.asset_id = str[index:to]
            index += len(self.asset_id) + 1
        else:
            self.asset_id = str[index:]
            index += len(self.asset_id)
        return index

    def parse_property_path(self, str, index):
        if index >= len(str):
            return index
        self.property_path = str[index:]
        index += len(self.property_path)
        return index

    def decode_components(self):
        self.node_path = urllib.parse.unquote(self.node_path)
        self.file_path = urllib.parse.unquote(self.file_path)
        self.asset_id = urllib.parse.unquote(self.asset_id)
        self.property_path = urllib.parse.unquote(self.property_path)


