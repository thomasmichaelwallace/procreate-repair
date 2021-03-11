"""Common utilities"""

import json
import plistlib


def uid_convert(obj):
    """To JSON uid convertor"""
    if isinstance(obj, plistlib.UID):
        return "UID(" + str(obj.data) + ")"
    # return obj

def format_bytes(size: int) -> str:
    """Return a number in human readable bytesize"""
    power = 2**10 # 2**10 = 1024
    index = 0
    power_labels = {0 : '', 1: 'k', 2: 'm', 3: 'g', 4: 't'}
    while size > power:
        size /= power
        index += 1
    return str(int(size)) + power_labels[index] + 'b'

def plist_to_json(data: bytes, filename) -> None:
    """Write plist as json"""
    plist = plistlib.loads(data)
    with open(filename + '.plist.json', 'w') as json_file:
        json.dump(plist, json_file, default=uid_convert)
