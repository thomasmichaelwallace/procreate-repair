"""Render a partially recovered procreate layer."""
import json
import math
import zlib

import lzo

from .chkdir import ChkDirReader
from .layer_writer import write_layer

MAX_BUFFER_LEN = 512*512*4 # posit largest size

def deflate_range(reader: ChkDirReader, start: int, end: int, allow_error: bool = False) -> bytes:
    """Deflate a chkdir range to memory."""
    reader.seek(start + 26)
    name_len = int.from_bytes(reader.read(2), "little")
    ext_len = int.from_bytes(reader.read(2), "little")
    reader.seek(name_len + ext_len, 1)

    size = end - reader.offset
    data = reader.read(size)

    try:
        decompress = zlib.decompressobj(-zlib.MAX_WBITS)
        deflated = decompress.decompress(data)
        deflated += decompress.flush()
        return deflated
    except: # pylint: disable=bare-except
        if allow_error:
            print('failed to deflate range ' + str(start) + '-' + str(end))
            return None
        else:
            raise

class ChunkRange:
    """A chunk range forming a layer"""
    def __init__(self, name: str, start: int, end: int) -> None:
        self.name = name
        self.start = start
        self.end = end
        self. layer_id = name.split('/')[0]
        location = name.split('/')[1].strip('.chunk').split('~')
        self.column = int(location[0])
        self.row = int(location[1])

def chunk_ranges_from_json(filename: str) -> list[ChunkRange]:
    """Loads chunk ranges from json def file"""
    chunks: list[ChunkRange] = []
    with open(filename, 'r') as file:
        data = json.load(file)
        for spec in data:
            name = spec['name']
            start = spec['start']
            end = spec['end']
            chunk = ChunkRange(name, start, end)
            chunks.append(chunk)
    return chunks


def get_tile_size(reader: ChkDirReader, chunks: list[ChunkRange]) -> int:
    """Gets the size of a square tile from an unknown chunk"""
    for chunk in chunks:
        data: bytes = deflate_range(reader, chunk.start, chunk.end, True)
        if  data is None:
            continue
        try:
            decompressed: bytes = lzo.decompress(data, False, MAX_BUFFER_LEN)
            pixel_count: float = len(decompressed) / 4 # RGBA per-pixel
            tilesize = math.sqrt(pixel_count) # square edge length
            return int(tilesize)
        except: # pylint: disable=bare-except
            continue
    return -1

def get_edge_size(reader: ChkDirReader, chunks: list[ChunkRange], tilesize: int) -> int:
    """Gets the size of an edge tile from an unknown chunk"""
    for chunk in chunks:
        data: bytes = deflate_range(reader, chunk.start, chunk.end, True)
        if data is None:
            continue
        try:
            decompressed: bytes = lzo.decompress(data, False, MAX_BUFFER_LEN)
            pixel_count: float = len(decompressed) / 4 # RGBA per-pixel
            edge_length = pixel_count / tilesize # rect edge length
            return int(edge_length)
        except: # pylint: disable=bare-except
            continue
    return -1

class ChunkArchive:
    """Emulate an archive from a chunk filesystem"""
    def __init__(self, reader: ChkDirReader, chunks: list[ChunkRange]) -> None:
        self.__reader = reader
        self.__chunks = chunks

    def namelist(self) -> list[str]:
        """A list of all the file names in the archive."""
        names = []
        for chunk in self.__chunks:
            names.append(chunk.name)
        return names

    def read(self, filename: str) -> bytes:
        """Return a deflated file by name"""
        the_chunk = None
        for chunk in self.__chunks:
            if chunk.name == filename:
                the_chunk = chunk
        if the_chunk is None:
            raise FileNotFoundError(filename)
        return deflate_range(self.__reader, the_chunk.start, the_chunk.end, True)


def write_partial_layer(out_file: str, reader: ChkDirReader, chunks: list[ChunkRange]):
    """Write a partial layer from a chunk archive"""
    archive = ChunkArchive(reader, chunks)
    layer_id = chunks[0].layer_id

    # get grid extents
    rows: int = 0
    columns: int = 0
    for chunk in chunks:
        if chunk.row > rows:
            rows = chunk.row
        if chunk.column > columns:
            columns = chunk.column

    # get representative chunks
    side_chunks: list[ChunkRange] = []
    mid_chunks: list[ChunkRange] = []
    base_chunks: list[ChunkRange] = []
    corner_chunk: ChunkRange = None
    for chunk in chunks:
        if chunk.row == rows and chunk.column != columns:
            base_chunks.append(chunk)
        if chunk.row != rows and chunk.column == columns:
            side_chunks.append(chunk)
        if corner_chunk is None and chunk.row == rows and chunk.column == columns:
            corner_chunk = chunk
        if chunk.row != rows and chunk.column != columns:
            mid_chunks.append(chunk)

    # chunk names are zero indexed
    rows += 1
    columns += 1

    tilesize = -1
    tilesize = get_tile_size(reader, mid_chunks)
    if tilesize < 0:
        print('warning - no mid tile found; infering size')
        tilesize = get_tile_size(reader, side_chunks)
        if tilesize < 0:
            tilesize = max(tilesize, get_tile_size(reader, base_chunks))
        if tilesize < 0 and corner_chunk:
            tilesize = max(tilesize, get_tile_size(reader, [corner_chunk]))

    if tilesize < 0:
        tilesize = 256
        print("no valid tile size found, guessing " + str(tilesize))


    # prefer to take from side elements
    edge_width = get_edge_size(reader, side_chunks, tilesize)
    base_height = get_edge_size(reader, base_chunks, tilesize)
    # else use one side and the corner
    if (edge_width < 0 and base_height > 0 and corner_chunk):
        edge_width = get_edge_size(reader, [corner_chunk], base_height)
    elif (base_height < 0 and edge_width > 0 and corner_chunk):
        base_height = get_edge_size(reader, [corner_chunk], edge_width)
    # assume exact tile fit and create edge-bleed as worse-case
    if edge_width < 0:
        edge_width = tilesize
    if base_height < 0:
        base_height = tilesize

    imagesize = [
        (columns - 1) * tilesize + edge_width,
        (rows - 1) * tilesize + base_height]

    # these options cannot be inferred:
    orientation = 1
    h_flipped = False
    v_flipped = False

    print('writing layer ' + layer_id +
        ' (' + str(columns) + '/' + str(imagesize[0]) +
        ',' + str(rows) + '/' + str(imagesize[1]) + ') ' +
        str(len(chunks)) + '@' + str(tilesize))

    write_layer(
        out_file, archive,
        layer_id,
        imagesize, tilesize,
        orientation, h_flipped, v_flipped,
        False
    )

def recover_manifest(filename: str, reader: ChkDirReader, start: int = 0):
    """
    Given a manifest json file of [filename] pointing to layer files of [{ name, start, end }],
    return all the layers rendered as .png.
    """
    with open(filename, 'r') as file:
        manifest: list[str] = json.load(file)
    manifest = manifest[start:]
    index = start
    for chunk_file in manifest:
        chunks = chunk_ranges_from_json(chunk_file)
        out_file = chunk_file.replace('/json/', '/png/').replace('.json', '.png')
        print('manifest no: ' + str(index) + "/" + str(len(manifest)))
        write_partial_layer(out_file, reader, chunks)
        index += 1
