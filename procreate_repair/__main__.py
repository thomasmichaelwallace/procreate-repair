"""Repair Procreate Files"""

from procreate_repair import recover_embedded

from . import (chkdir, deflate, detect_zip, partial_layer_writer,
               procreate_drawing, recover_embedded)

CHK_DIR_NAME = '../chunks'

def main(step: int, preview: bool = True):
    """Example structure for recovering procreate files"""
    # recommended usage:
    if step == 0:
        # detect zips
        detect_zip.detect_zip(CHK_DIR_NAME)
        # move zip json to -> ./resources/recovered/partials.fragments.json
        # move unknown json to ->  ./resources/unknown/partials.unknown.json
    elif step == 1:
        sub_dir = 'preview' if preview else 'files'
        # develop previews/files of totally recovered ranges
        recover_embedded.recover_range_file('./resources/recovered/partials.fragments.json',
            CHK_DIR_NAME, './resources/embedded/' + sub_dir, preview)

    # see ./scripts/complete.js for more information on developing the intermediate files
    elif step == 2:
        # extract procreate configuration files for further analysis
        deflate.deflate_ranges('./resources/recovered/archives/ranges.json', CHK_DIR_NAME,
            './resources/archives')
    elif step == 3:
        # extract partial procreate files as full directories
        # then compress them as .zip
        for index in [1, 2, 3]: # block numbers
            print("rebuilding " + str(index))
            json_file = './resources/recovered/implied' + '/block.' + str(index) + '.json'
            out_dir = './resources/recovered/implied' + '/' + str(index) + '/'
            deflate.deflate_ranges(json_file, CHK_DIR_NAME, out_dir)
    elif step == 3:
        # extract preview image
        for index in [1, 2, 3]: # block numbers
            print('previewing ' + str(index))
            zip_file = './resources/recovered/implied' + '/' + str(index) + '/Archive.zip'
            out_file = './resources/recovered/implied' + '/recover-' + str(index) + '.png'
            with open(zip_file, 'rb') as file:
                drawing = procreate_drawing.ProcreateDrawing(file)
                drawing.write_layer(drawing.composite_uuid, out_file)
    elif step == 4:
        # recover layers as png
        reader = chkdir.ChkDirReader(CHK_DIR_NAME)
        partial_layer_writer.recover_manifest('./resources/recovered/layers/manifest.json', reader)

# main(0)
