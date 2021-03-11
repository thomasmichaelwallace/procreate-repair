"""Utilities to recover whole, but embedded, procreate drawings from a chkdir"""
import io
import json
import os

from .chkdir import ChkDirReader
from .procreate_drawing import ProcreateDrawing


def recover_range(
    reader: ChkDirReader, start: int, end: int, out_dir: str, preview_mode: bool = False
) -> None:
    """Recover a procreate file from a chkdir"""
    print('reading ' + str(start) + '-' + str(end))
    reader.seek(start, 0)
    raw = reader.read(end - start)
    data = io.BytesIO(raw)
    procreate = ProcreateDrawing(data)
    if procreate.validate():
        print('validated procreate file')
        if not preview_mode:
            procreate.write_file(os.path.join(out_dir, procreate.name + '.procreate'))
            preview_name = procreate.name + '.preview.png'
        else:
            preview_name = str(start) + '.preview.png'
        procreate.write_layer(procreate.composite_uuid, os.path.join(out_dir, preview_name))
    else:
        print('skipping invalid drawing')

def recover_ranges(
    chk_dirname: str, ranges: list[tuple[int, int]], out_dir: str, preview_mode: bool = False
) -> None:
    """Recover a set of procreate file ranges from a chkdir"""
    reader = ChkDirReader(chk_dirname)
    for [start, end] in ranges:
        if not preview_mode:
            sub_dir = os.path.join(out_dir, str(start))
        else:
            sub_dir = out_dir
        os.makedirs(sub_dir, exist_ok=True)
        recover_range(reader, start, end, sub_dir, preview_mode)
    reader.close()

def recover_range_file(filename: str, chk_dirname: str, out_dir: str, preview_mode = False) -> None:
    """
    Given a JSON file of [{ valid, start, end }], generate procreate files (or previews) embedded
    in the chkdir at [start]-[end] if [valid].
    """
    with open(filename, 'r') as file:
        range_file = json.load(file)
    ranges: list[tuple[int, int]] = []
    for range_json in range_file:
        if range_json['valid'] is True:
            ranges.append([range_json['start'], range_json['end']])
    ranges = [ranges[-1]]
    print('discovered ' + str(len(ranges)) + ' files')
    recover_ranges(chk_dirname, ranges, out_dir, preview_mode)
