from .node import Node


class NodeLibrary:
    def __init__(self, asset, json_asset):
        self.asset = asset
        self.nodes = {}
        self.parse(json_asset)

    def parse(self, json_asset):
        for json_node in json_asset.get("node_library", []):
            node = Node(self.asset)
            node.parse(json_node)
            self.nodes[node.id] = node

    def find(self, id):
        return self.nodes.get(id, None)

