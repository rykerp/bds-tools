from .material import Channel
from .morph import Morph

class Modifier:
    def __init__(self, json_modifier):
        self.id = json_modifier["id"]
        self.name = json_modifier.get("name", self.id)
        self.parent = json_modifier.get("parent", None)
        self.type = "unknown"
        self.morph = None
        self.formulas = []
        self.skin = None
        self.channel = None
        if "channel" in json_modifier:
            self.channel = Channel(json_modifier)

        if "morph" in json_modifier:
            self.type = "morph"
            self.morph = Morph(json_modifier["morph"])

        if "formulas" in json_modifier:
            self.type = "morph"
            for json_formula in json_modifier["formulas"]:
                self.formulas.append(Formula(json_formula))

        if "skin" in json_modifier:
            self.type = "skin"
            self.skin = Skin(json_modifier["skin"])


class Formula:
    def __init__(self, json_formula):
        self.output = json_formula["output"]
        self.operations = [Operation(json_operation) for json_operation in json_formula["operations"]]
        self.stage = json_formula.get("stage", "sum")


class Operation:
    def __init__(self, json_operation):
        self.op = json_operation["op"]
        self.val = json_operation.get("val", None)
        self.url = json_operation.get("url", None)


class Skin:
    def __init__(self, json_skin):
        self.node = json_skin["node"]
        self.geometry = json_skin["geometry"]
        self.joints = {}
        for json_joint in json_skin.get("joints", []):
            joint = Joint(json_joint)
            self.joints[joint.node] = joint


class Joint:
    def __init__(self, json_joint):
        self.id = json_joint["id"]
        self.node = json_joint["node"]
        self.local_weights = None
        self.node_weights = None
        if "local_weights" in json_joint:
            self.local_weights = {
                "x": json_joint["local_weights"].get("x", {}).get("values", []),
                "y": json_joint["local_weights"].get("z", {}).get("values", []),
                "z": json_joint["local_weights"].get("y", {}).get("values", [])
            }
        if "node_weights" in json_joint:
            self.node_weights = json_joint["node_weights"]["values"]
