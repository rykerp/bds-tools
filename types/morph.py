class Morph:
    def __init__(self, json_morph):
        self.vertex_count = json_morph["vertex_count"]
        self.vertex_deltas = json_morph["deltas"]["values"]
