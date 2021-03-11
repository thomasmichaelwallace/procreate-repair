"""Layer utilities"""
import math
from zipfile import ZipFile

import lzo
from PIL import Image

# this code owes an incredible amount to:
#  - https://github.com/jaromvogel/ProcreateViewer
#  - https://github.com/redstrate/procreate-viewer

def process_chunk(
    archive: ZipFile,
    layer_id: str, chunk_name: str,
    imagesize: list[int], tilesize: int,
    columns: int, rows: int,
    difference_x: int, difference_y: int,
    strict: bool
) -> tuple[Image.Image, tuple[int, int]]:
    """iterate through chunks, decompress them, create images"""
    # Get row and column from filename
    column = int(chunk_name.strip('.chunk').split('~')[0])
    row = int(chunk_name.strip('.chunk').split('~')[1]) + 1
    chunk_tilesize = {
        "x": tilesize,
        "y": tilesize
    }

    # Account for columns or rows that are too short
    if (column + 1) == columns:
        chunk_tilesize['x'] = tilesize - difference_x
    if row == rows:
        chunk_tilesize['y'] = tilesize - difference_y

    try:
        # read the actual data and create an image
        file = archive.read(layer_id + '/' + chunk_name)
        # 262144 is the final byte size of the pixel data for 256x256 square.
        # This is based on 256*256*4 (width * height * 4 bytes per pixel)
        # finalsize is chunk width * chunk height * 4 bytes per pixel
        finalsize = chunk_tilesize['x'] * chunk_tilesize['y'] * 4
        decompressed = lzo.decompress(file, False, finalsize)
        # Will need to know how big each tile is instead of just saying 256
        image = Image.frombytes('RGBA', (chunk_tilesize['x'],chunk_tilesize['y']), decompressed)
        # Tile starts upside down, flip it
        image = image.transpose(Image.FLIP_TOP_BOTTOM)

        # Calculate pixel position of tile
        position_x = column * tilesize
        position_y = (imagesize[1] - (row * tilesize))
        if  row == rows:
            position_y = 0

        return (image, (position_x, position_y))
    except: # pylint: disable=bare-except
        if strict:
            raise
        print("failed to decompress: " + layer_id + '/' + chunk_name)
        return None

def write_layer(
    out_file: str, archive: ZipFile,
    layer_id: str,
    imagesize: tuple[int, int], tilesize: int,
    orientation: int, h_flipped: bool, v_flipped: bool,
    strict: bool = True
):
    """Write a layer to a bitmap"""
    # detect files
    all_files = archive.namelist()
    layer_files = list(filter(lambda x: layer_id in x, all_files))
    chunk_list = list(map(lambda x: x.strip(layer_id).strip('/'), layer_files))

    # create a new image
    canvas = Image.new('RGBA', (imagesize[0], imagesize[1]))

    # Figure out how many total rows and columns there are
    columns = int(math.ceil(float(imagesize[0]) / float(tilesize)))
    rows = int(math.ceil(float(imagesize[1]) / float(tilesize)))

    # Calculate difference-x and difference-y
    difference_x = 0
    difference_y = 0
    if imagesize[0] % tilesize != 0:
        difference_x = (columns * tilesize) - imagesize[0]
    if imagesize[1] % tilesize != 0:
        difference_y = (rows * tilesize) - imagesize[1]

    tilelist = []
    # print(chunk_list)
    for chunk_name in chunk_list:
        if (chunk_name == '' and not strict):
            continue
        response = process_chunk(
            archive,
            layer_id, chunk_name,
            imagesize, tilesize,
            columns, rows,
            difference_x, difference_y,
            strict)
        if response is not None:
            tilelist.append(response)

    # Add each tile to composite image
    for tile in tilelist:
        canvas.paste(tile[0], tile[1])

    # Make sure the image appears in the correct orientation
    if orientation == 3:
        canvas = canvas.rotate(90, expand=True)
    elif orientation == 4:
        canvas = canvas.rotate(-90, expand=True)
    elif orientation == 2:
        canvas = canvas.rotate(180, expand=True)

    if h_flipped == 1 and (orientation == 1 or orientation == 2):
        canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)
    if h_flipped == 1 and (orientation == 3 or orientation == 4):
        canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
    if v_flipped == 1 and (orientation == 1 or orientation == 2):
        canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
    if v_flipped == 1 and (orientation == 3 or orientation == 4):
        canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)

    canvas.save(out_file)
