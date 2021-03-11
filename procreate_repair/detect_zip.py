"""Detect zip files in chkdir streams"""
from enum import Enum
from typing import Union

from json_tricks import dump

from .chkdir import ChkDirReader
from .utils import format_bytes

PK_ZIP_FILE_HEADER = bytes([0x50, 0x4b, 0x3, 0x4])
PK_ZIP_DIR_HEADER = bytes([0x50, 0x4b, 0x1, 0x2])
PK_ZIP_EOF_HEADER = bytes([0x50, 0x4b, 0x5, 0x6])
EMPTY_BYTES = bytes([0])

class Block(Enum):
    """Chunk block types"""
    UNKNOWN = 1
    FILE = 2
    DIR = 3
    EOF = 4

class ZipFileFragment:
    """Potential zipped file"""
    def __init__(
        self,
        start: int, end: int,
        name: str,
        last_modified: tuple[int, int]
    ) -> None:
        self.__start = start
        self.__end = end
        self.__name = name
        self.__last_modified = last_modified
        self.__corrupt_offset = -1

    def __str__(self) -> str:
        return self.__name + " (" + str(self.__start) + "-" + str(self.__end) + ")"

    def __json_encode__(self):
        return {
            'start': self.__start,
            'end': self.__end,
            'name': self.__name,
            'fid': self.__name + "/" + str(self.__last_modified),
            'corrupt': self.__corrupt_offset
        }

    @property
    def name(self) -> str:
        """Zipped file name"""
        return self.__name
    @property
    def start(self) -> int:
        """File start"""
        return self.__start

    def mark_corrupt(self, offset) -> None:
        """Mark first known corrupt offset"""
        self.__corrupt_offset = offset


class ZipDirFragment:
    """Potential central directory record"""
    def __init__(
        self,
        start: int, end: int,
        name: str,
        last_modified: tuple[int, int],
        file_offset: tuple[int, int],
    ) -> None:
        self.__start = start
        self.__end = end
        self.__name = name
        self.__last_modified = last_modified
        self.__file_offset = file_offset
        self.__corrupt_offset = -1

    def __str__(self) -> str:
        return self.__name + " (" + str(self.__start) + "-" + str(self.__end) + ")"

    def __json_encode__(self):
        return {
            'name': self.__name,
            'ref': self.__name + "/" + str(self.__last_modified),
            'offset': self.__file_offset,
            'corrupt': self.__corrupt_offset
        }

    @property
    def name(self) -> str:
        """Record entry name"""
        return self.__name

    def mark_corrupt(self, offset) -> None:
        """Mark first known corrupt offset"""
        self.__corrupt_offset = offset


class ZipFragment:
    """Potential complete zip archive"""
    def __init__(self) -> None:
        self.__files: list[ZipFileFragment] = []
        self.__dirs: list[ZipDirFragment] = []
        self.__start: int = -1
        self.__end: int = -1
        self.__eof_start: int = -1
        self.__eof_end: int = -1
        self.__eof_dir_count: int = -1
        self.__dir_start = -1
        self.__zip_start = -1
        self.__last: Union[ZipDirFragment, ZipFileFragment] = None

    def __str__(self) -> str:
        return  "zip file (" + str(self.__start) + "-" + str(self.__end) + ")"

    def __json_encode__(self):
        valid = self.validate(False)
        json_dict = {
            'start': self.__start,
            'end': self.__end,
            'valid': valid,
            "zip_start": self.__zip_start,
            "dir_start": self.__dir_start,
            "dir_count": self.__eof_dir_count,
        }
        if not valid:
            files = map(lambda f: f.__json_encode__(), self.__files)
            dirs = map(lambda d: d.__json_encode__(), self.__dirs)
            json_dict['files'] = list(files)
            json_dict['dirs'] = list(dirs)
        return json_dict


    def add_file(self, file: ZipFileFragment) -> None:
        """Add a file to the archive"""
        if self.__start == -1:
            self.__start = file.start
        self.__files.append(file)
        self.__last = file

    def add_dir(self, zip_dir: ZipDirFragment) -> None:
        """Add a directory record to the archive"""
        self.__dirs.append(zip_dir)
        self.__last = zip_dir

    def add_eof(
        self,
        start: int, end: int,
        dir_count: str,
        dir_start: int, zip_start: int
    ) -> None:
        """Adds end of central directory record to zip"""
        self.__end = end
        self.__eof_start = start
        self.__eof_end = end
        self.__eof_dir_count = dir_count
        self.__dir_start = dir_start
        self.__zip_start =zip_start

    def validate(self, verbose: bool = True) -> bool:
        """Returns true if zip file appears to be valid"""
        dir_count = self.__eof_dir_count == len(self.__dirs)
        if (verbose and not dir_count):
            print('[validate]: dir count got: '
                + str(len(self.__dirs)) + ", expected: " + str(self.__eof_dir_count))
        file_names = map(lambda f: f.name, self.__files)
        dir_names = map(lambda d: d.name, self.__dirs)
        missing_files: list[str] = []
        for zip_dir in dir_names:
            if not any(zip_dir in f for f in file_names):
                missing_files.append(zip_dir)
        if (verbose and len(missing_files) > 0):
            print('[validate]: missing ' + str(len(missing_files)))
             # + " files:\n" + str(missing_files))
        extra_files: list[str] = []
        for zip_file in file_names:
            if not any(zip_file in d for d in dir_names):
                extra_files.append(zip_file)
        if (verbose and len(extra_files) > 0):
            print('[validate]: extra ' + str(len(extra_files)))
             #  + " files:\n" + str(extra_files))
        return dir_count and len(missing_files) == 0 and len(extra_files) == 0

    def likely(self, verbose: bool = True) -> bool:
        """Returns true if was likely a zip fragment"""
        if (verbose and len(self.__files) > 1):
            # file_names = map(lambda f: f.name, self.__files)
            print('[likely]: zip includes multiple files:' + str(len(self.__files)))
            # print(list(file_names))
            return True
        # print('[likely]: named as ' + self.__files[0].name)
        return False

    def mark_corrupt(self, offset) -> None:
        """Mark first known corrupt offset"""
        if  self.__last:
            self.__last.mark_corrupt(offset)


class UnknownFragment:
    """Unknown stream of bytes"""
    def __init__(self, start: int, end: int, magic: bytearray, rollback: bool) -> None:
        self.__start = start
        self.__end = end
        self.__magic = bytes(magic)
        self.__rollback = rollback

    def __str__(self) -> str:
        return  "unknown " + str(self.__start) + "/" + format_bytes(self.__end - self.__start) + (
            " [rollback]" if self.__rollback else "")

    def __json_encode__(self):
        return {
            'start': self.__start,
            'end': self.__end,
            'magic': self.__magic.hex()
        }

class UnknownFragments:
    """Unknown data fragment collector"""

    __GAP_LENGTH: int = 512

    def __init__(self) -> None:
        self.__fragment_start: int = -1
        self.__fragment_end: int  = -1
        self.__empty_len: int = 0
        self.__fragments: list[UnknownFragment] = []
        self.__magic = bytearray()
        self.__rollback = False

    def __json_encode__(self):
        fragments = map(lambda f: f.__json_encode__(), self.__fragments)
        return list(fragments)

    def process(self, data: bytes, offset: int) -> None:
        """Processes unknown bytes to fragments"""
        is_empty = data == EMPTY_BYTES
        if (is_empty and self.__fragment_start < 0):
            return

        if  self.__fragment_start < 0:
            self.__magic.clear()
            self.__fragment_start = offset

        if len(self.__magic) < 4:
            self.__magic.extend(data)

        if is_empty:
            # allow __GAP_LENGTH of empty bytes in an unknown fragment
            self.__empty_len += 1
            if self.__empty_len >= UnknownFragments.__GAP_LENGTH:
                self.__flush()
                return
        else:
            self.__empty_len = 0

        self.__fragment_end = offset

    def undo_header(self) -> None:
        """Undo last four bytes as known header"""
        if  self.__fragment_end > -1:
            # unknown data stream was processed
            self.__fragment_end -= 4
            if  self.__fragment_start < self.__fragment_end:
                self.__flush()
            else:
                self.__fragment_start = -1
                self.__fragment_end = -1
                self.__rollback = False

    def rollback(self) -> None:
        """Rollback unknown"""
        self.__fragment_start = -1
        self.__fragment_end = -1
        self.__rollback = True

    def eof(self) -> None:
        """Register EOF fragments"""
        if self.__fragment_end > -1:
            self.__flush()

    def __flush(self) -> None:
        self.__fragment_end -= self.__empty_len # headers are not empty, so flush will still be ok
        fragment = UnknownFragment(
            self.__fragment_start, self.__fragment_end, self.__magic, self.__rollback)
        print(fragment)
        self.__rollback = False
        self.__fragments.append(fragment)
        self.__fragment_start = -1
        self.__fragment_end = -1

def detect_zip(dirname: str) -> None:
    """
    Given a directory of .CHK files return:
     - ./partials.zips.json : json encoded zip ranges (see ZipFragment)
     - ./partials.unknown.json : json encoded unknown ranges (see UnknownFragments)
    See ./scripts/complete.js for ways of working with this data.
    """
    reader = ChkDirReader(dirname) # read/seek chunk
    last_reported_progress = 0

    state: Block = Block.UNKNOWN
    header_buffer: bytearray = bytearray()

    zip_fragment = None
    unknown_fragments = UnknownFragments()

    block_start = 0

    zip_fragments=[]

    while reader.offset < reader.size:
        # build header
        data = reader.read(1)

        progress =  (reader.offset * 100) // reader.size
        if  progress != last_reported_progress:
            print('[progress]: ' + str(progress) + '%')
            last_reported_progress = progress

        header_buffer.extend(data)
        if len(header_buffer) > 4:
            header_buffer.pop(0)

        if header_buffer == PK_ZIP_FILE_HEADER:
            header_buffer.clear()
            unknown_fragments.undo_header()
            block_start = reader.offset - 4 # include header
            if state != Block.FILE:
                # start of zip file
                if state != Block.UNKNOWN:
                    print('unexpected FILE state from ' + str(state) + ' @' + str(reader.offset))
                state = Block.FILE
                if zip_fragment is not None:
                    print('persisting partial zip fragment')
                    zip_fragment.mark_corrupt(reader.offset)
                    zip_fragments.append(zip_fragment)
                    zip_fragment = ZipFragment()
                zip_fragment = ZipFragment()
            reader.seek(6, 1) # o+10
            lm_time = int.from_bytes(reader.read(2), "little")
            lm_date = int.from_bytes(reader.read(2), "little")
            reader.seek(4, 1) # o+18
            compressed_len = int.from_bytes(reader.read(4), "little")
            reader.seek(4, 1) # o+26
            name_len = int.from_bytes(reader.read(2), "little")
            ext_len = int.from_bytes(reader.read(2), "little")
            name = reader.read(name_len).decode("utf-8", "replace")
            reader.seek(ext_len + compressed_len, 1) # to end of block
            file = ZipFileFragment(block_start, reader.offset, name, [lm_date, lm_time])
            zip_fragment.add_file(file)

        elif header_buffer == PK_ZIP_DIR_HEADER:
            header_buffer.clear()
            unknown_fragments.undo_header()
            block_start = reader.offset - 4 # include header
            if state != Block.DIR:
                # start of central directory structure
                if state != Block.FILE:
                    print('unexpected DIR state from ' + str(state) + ' @' + str(reader.offset))
                    if zip_fragment is not None:
                        print('persisting partial zip fragment')
                        zip_fragment.mark_corrupt(reader.offset)
                        zip_fragments.append(zip_fragment)
                    zip_fragment = ZipFragment()
                state = Block.DIR
            reader.seek(8, 1) # o+12
            lm_time = int.from_bytes(reader.read(2), "little")
            lm_date = int.from_bytes(reader.read(2), "little")
            reader.seek(4, 1) # o+20
            compressed_len = int.from_bytes(reader.read(4), "little")
            reader.seek(4, 1) # o+28
            name_len = int.from_bytes(reader.read(2), "little")
            ext_len = int.from_bytes(reader.read(2), "little")
            com_len = int.from_bytes(reader.read(2), "little")
            reader.seek(8, 1) # o+42
            relative_file_start = int.from_bytes(reader.read(4), "little")
            relative_file_end = relative_file_start + compressed_len
            name = reader.read(name_len).decode("utf-8", "replace")
            reader.seek(ext_len + com_len, 1) # to end of block
            zip_dir = ZipDirFragment(block_start, reader.offset, name,
                [lm_date, lm_time], [relative_file_start, relative_file_end])
            zip_fragment.add_dir(zip_dir)

        elif header_buffer == PK_ZIP_EOF_HEADER:
            header_buffer.clear()
            unknown_fragments.undo_header()
            block_start = reader.offset - 4 # include header
            if state != Block.DIR:
                # start of end of file header, there is only one
                print('unexpected EOF state from ' + str(state) + ' @' + str(reader.offset))
                if zip_fragment is not None:
                    print('persisting partial zip fragment')
                    zip_fragment.mark_corrupt(reader.offset)
                    zip_fragments.append(zip_fragment)
                    zip_fragment = ZipFragment()
            state = Block.EOF
            reader.seek(6, 1) # o+10
            dir_count = int.from_bytes(reader.read(2), "little")
            dir_size = int.from_bytes(reader.read(4), "little")
            dir_offset = int.from_bytes(reader.read(4), "little")
            dir_start = block_start - dir_size
            zip_start = dir_start - dir_offset
            com_len = int.from_bytes(reader.read(2), "little")
            reader.seek(com_len, 1) # to end of block
            zip_fragment.add_eof(block_start, reader.offset, dir_count, dir_start, zip_start)
            print(zip_fragment)
            zip_fragment.validate()
            zip_fragments.append(zip_fragment)
            zip_fragment = None

        else:
            unknown_fragments.process(data, reader.offset)
            if len(header_buffer) >= 4: # let buffer fill before calling empty/data
                if state != Block.UNKNOWN:
                    if state == Block.FILE:
                        print('partial zip @' + str(reader.offset))
                        zip_fragment.likely()
                        zip_fragment.mark_corrupt(reader.offset)
                        zip_fragments.append(zip_fragment)
                        zip_fragment = None
                        reader.seek(block_start + 1)
                        print('rolling back @' + str(reader.offset))
                        unknown_fragments.rollback()
                    elif state != Block.EOF:
                        print('unexpected UNKNOWN state from '
                            + str(state) + ' @' + str(reader.offset))
                        reader.seek(block_start + 1)
                        print('rolling back @' + str(reader.offset))
                        unknown_fragments.rollback()
                    state = Block.UNKNOWN

    unknown_fragments.eof()
    if zip_fragment:
        zip_fragment.mark_corrupt(reader.size)
        zip_fragments.append(zip_fragment)

    dump(zip_fragments, './partials.zips.json', primitives=True, indent=2)
    dump(unknown_fragments, './partials.unknown.json', primitives=True, indent=2)
    return [zip_fragments, unknown_fragments]
