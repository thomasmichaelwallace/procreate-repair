"""Utilities to extract embedded zip data from chkdirs"""
import json
import os
import zlib

from .chkdir import ChkDirReader

# from os import read

def deflate_range(outfile: str, reader: ChkDirReader, start: int, end: int) -> None:
    """Extract and decompress a range from a chkdir"""
    reader.seek(start + 26)
    name_len = int.from_bytes(reader.read(2), "little")
    ext_len = int.from_bytes(reader.read(2), "little")
    reader.seek(name_len + ext_len, 1)

    size = end - reader.offset
    data = reader.read(size)

    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    inflated = decompress.decompress(data)
    inflated += decompress.flush()

    dirname = os.path.dirname(outfile)
    os.makedirs(dirname, exist_ok=True)

    with open(outfile, 'xb') as file:
        file.write(inflated)
    # plist_to_json(inflated, outfile)

def deflate_ranges(filename: str, dirname: str, prefix: str) -> None:
    """
    Given a json file of [{ file, start, end }] ranges, extract the range [start]-[end]
    from a chkdir, deflate and save the decompressed contents to [file]
    """
    reader = ChkDirReader(dirname)

    with open(filename, 'r') as file:
        ranges = json.load(file)

    for fragment in ranges:
        start: int = fragment['start']
        end: int = fragment['end']
        out_file: str = prefix + fragment['file']
        deflate_range(out_file, reader, start, end)
