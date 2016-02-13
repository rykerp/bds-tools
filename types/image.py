class Image:
    def __init__(self, json_image):
        self.id = json_image["id"]
        self.name = json_image.get("name", "")
        self.map_gamma = json_image.get("map_gamma", 0)
        self.map_url = None
        map = json_image.get("map", None)
        if map and len(map) > 0:
            self.map_url = map[0]["url"]
