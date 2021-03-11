"""Work with a directory of .CHK files as a single readable stream"""

from os import listdir
from os.path import getsize, isfile, join
from typing import BinaryIO, Union

from .utils import format_bytes


class ChkDirReader:
    """Exposes a directory of files as a continuos stream"""
    def __init__(self, dirname: str) -> None:
        filenames = [f for f in listdir(dirname) if isfile(join(dirname, f))]
        filenames.sort() # chunks are in alphabetical order
        self.__filenames: list[str] = [] # filenames by index
        self.__ranges: list[tuple[int, int]] = [] # [inc. start, exc. end] offset ranages by index
        offset = 0
        for filename in filenames:
            start = offset
            fullpath = join(dirname, filename)
            self.__filenames.append(fullpath)
            offset += getsize(fullpath)
            self.__ranges.append([start, offset])

        self.__size: int = offset # exclusive offset maximum
        self.__offset: int = 0 # next read pointer
        self.__index: int = -1 # open file index, -1 if none
        self.__file: Union[BinaryIO, None] = None
        self.__open(0) # open file

    @property
    def size(self) -> int:
        """Total size"""
        return self.__size

    @property
    def offset(self) -> int:
        """Next read position"""
        return self.__offset

    def close(self) -> None:
        """Closes any open handles"""
        self.__index = -1
        if  self.__file:
            self.__file.close()
            self.__file = None

    def __open(self, index: int) -> None:
        if (index < 0 or index >= len(self.__filenames)):
            # out of bounds, close file
            self.close()
            return
        if index == self.__index:
            # re-requested open file
            self.__file.seek(0)
            return

        # else chunk file has changed:
        self.close() # clear up
        self.__index = index

        filename = self.__filenames[self.__index]
        [start, end] = self.__ranges[self.__index]
        print('[chunk] ' + filename + " (" + format_bytes(end - start) + ")")

        self.__file = open(filename, 'rb')

    def seek(self, offset: int, mode: int = 0) -> int:
        """
        Seek to a position in the file.
        Mode specifies how the offset is defined:
            - 0: relative to start of directory (default)
            - 1: relative to last read position
            - 2: relative to end of directory
            - 3: relative to start of current file
            - 4: relative to start of next file
        """
        if mode == 1:
            self.__offset += offset
        elif mode == 2:
            self.__offset = (self.__size - 1) - offset
        elif mode == 3:
            self.__offset = self.__ranges[self.__index][0] + offset
        elif mode == 4:
            self.__offset = self.__ranges[self.__index][1] + offset
        else: # mode==0
            self.__offset = offset

        if (self.__offset < 0 or self.__offset >= self.__size):
            # out of range
            self.close()
            return self.__offset

        if  self.__index > -1:
            # shortcut for common cases
            [start, end] = self.__ranges[self.__index]
            if (self.__offset >= start and self.__offset < end):
                # file has not changed
                self.__file.seek(self.__offset - start)
                return self.__offset
            if (self.__offset == end and self.__index + 1 < len(self.__ranges)):
                # next file byte
                self.__open(self.__index + 1)
                self.__file.seek(0)
                return self.__offset

        for i in range(len(self.__ranges)):
            [start, end] = self.__ranges[i]
            if (self.__offset >= start and self.__offset < end):
                self.__open(i) # update index, and repoint chunk file
                self.__file.seek(self.__offset - start)
                return self.__offset

        # indicates that offset cannot be found within the ranges, should be impossible:
        raise Exception("Seek failed because of inconsistent chunk internals")

    def read(self, length: int) -> bytes:
        """Read length number of bytes inclusive of the current offset"""
        remaining = length

        if self.__offset >= self.__size:
            # out of range
            self.seek(0, self.__offset + length)
            return bytes()

        if self.__offset < 0:
            # exhaust to seek to zero
            remaining += self.__offset
            if remaining >= 0:
                self.seek(0, 0)

        stack: bytearray = bytearray()
        while remaining > 0:
            data = self.__file.read(remaining)
            stack.extend(data)
            data_len = len(data)
            remaining -= data_len

            if  remaining == 0:
                # keep offset consistent
                self.__offset += data_len
            elif remaining > 0:
                # roll to next file
                if self.__index + 1 < len(self.__ranges):
                    # data remains to be read, seek to next chunk
                    self.seek(0, 4)
                else:
                    # out of range
                    self.seek(remaining + data_len, 1)
                    remaining = 0
            else:
                # negative remainder, should be impossible:
                raise Exception("Read failed because of inconsistent chunk internals")

        return bytes(stack)
