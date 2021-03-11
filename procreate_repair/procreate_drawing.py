"""A procreate drawing"""
import json
import plistlib
import re
import zipfile
from io import BytesIO

from .layer_writer import write_layer
from .utils import uid_convert


class ProcreateDrawing:
    """A procreate drawing"""
    def __init__(self, data: BytesIO) -> None:
        self.__raw = data
        archive = zipfile.ZipFile(data, 'r')
        self.data = archive
        plist_data = archive.read('Document.archive')
        plist = plistlib.loads(plist_data)
        self.plist = plist
        self.__objects = self.plist.get('$objects')
        self.__root_object = self.__objects[1]

    @property
    def tile_size(self) -> int:
        """Drawing tile size"""
        return self.__root_object.get('tileSize')
    @property
    def orientation(self) -> int:
        """Drawing orientation"""
        return self.__root_object.get('orientation')
    @property
    def name(self) -> str:
        """Drawing name"""
        name_ref = self.__root_object.get('name').data
        return self.__objects[name_ref]
    @property
    def flipped_horizontally(self) -> bool:
        """If true drawing is flipped horizontally"""
        return self.__root_object.get('flippedHorizontally')
    @property
    def composite_uuid(self) -> str:
        """Uuid of the composite layer"""
        composite_ref = self.__root_object.get('composite').data
        uuid_ref = self.__objects[composite_ref].get('UUID')
        return self.__objects[uuid_ref]
    @property
    def __image_size(self) -> list[str]:
        size_ref = self.__root_object.get('size').data
        image_size_string = self.__objects[size_ref]
        image_size = image_size_string.strip('{').strip('}').split(', ')
        return image_size
    @property
    def width(self) -> int:
        """Drawing width"""
        return int(self.__image_size[0])
    @property
    def height(self) -> int:
        """Drawing height"""
        return int(self.__image_size[1])
    @property
    def flipped_vertically(self) -> bool:
        """If true drawing is flipped vertically"""
        return self.__root_object.get('flippedVertically')
    @property
    def layer_uuids(self) -> list[str]:
        """List of layer uuids"""
        layers_ref = self.__root_object.get('layers').data
        layers = self.__objects[layers_ref].get('NS.objects')
        layer_uuids = []
        for layer_ref in layers:
            layer = self.__objects[layer_ref.data]
            uuid = layer.get('UUID')
            layer_uuids.append(uuid)
        return layer_uuids
    @property
    def unwrapped_layer_uuids(self) -> list[str]:
        """List of layer uuids"""
        layers_ref = self.__root_object.get('unwrappedLayers').data
        layers = self.__objects[layers_ref].get('NS.objects')
        layer_uuids = []
        for layer_ref in layers:
            layer = self.__objects[layer_ref.data]
            uuid = layer.get('UUID')
            layer_uuids.append(uuid)
        return layer_uuids
    @property
    def all_uuids(self) -> list[str]:
        """List of all the uuids referenced"""
        uuids = []
        for obj in self.__objects:
            if isinstance(obj, str):
                is_uuid = re.fullmatch(
                    r"\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b",
                    obj, flags=re.IGNORECASE)
                if is_uuid:
                    uuids.append(obj)
        return uuids

    def validate(self) -> bool:
        """Validates all referenced data exists"""
        uuids = self.all_uuids
        print("testing for " + str(len(uuids)) + " resources")
        all_files = self.data.namelist()
        missing_count = 0
        for uuid in uuids:
            for file in all_files:
                if uuid in file: # only layer file
                    try:
                        self.data.read(file)
                    except IOError:
                        print('missing uuid: ' + uuid)
                        missing_count += 1
        return missing_count == 0

    def write_file(self, path):
        """Dump procreate to the file"""
        with open(path, 'xb') as file:
            file.write(self.__raw.getbuffer())

    def write_layer(self, layer_id, out_file):
        """Write a layer to disk"""
        return write_layer(
            out_file, self.data, layer_id,
            [self.width, self.height], self.tile_size,
            self.orientation, self.flipped_horizontally, self.flipped_vertically,
        )

    def write_json(self, filename):
        """Writes the plist out as a json file"""
        with open(filename + '.plist.json', 'w') as json_file:
            json.dump(self.plist, json_file, default=uid_convert)
