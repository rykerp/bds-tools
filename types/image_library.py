from .image import Image


class ImageLibrary:
    def __init__(self, asset, json_asset):
        self.asset = asset
        self.images = {}
        for json_image in json_asset.get("image_library", []):
            image = Image(json_image)
            self.images[image.id] = image

    def find(self, id):
        return self.images.get(id, None)