class UvSet:
    def __init__(self, json_uv_set):
        self.id = json_uv_set["id"]
        self.uvs = json_uv_set["uvs"]["values"]
        self.polygon_vertex_indices = json_uv_set["polygon_vertex_indices"]
        self.separate = {(t[0], t[1]): t[2] for t in self.polygon_vertex_indices}

    def get_uvs(self, face_index, verts):
        uvs = []
        for v in verts:
            if (face_index, v) in self.separate:
                uvidx = self.separate[(face_index, v)]
            else:
                uvidx = v
            uvs.append(self.uvs[uvidx])
        return uvs
