import struct
from typing import Literal

class JHashLookup2:
    _GOLDEN_RATIO = 0x9E3779B9
    def __init__(self, seed: int, endianness: Literal["little", "big", "None"]) -> None:
        t = {
            "little": "<",
            "big"   : ">",
            "None"  : ""
        }
        self._fmt = t[endianness] + "I"

        self._a = self._GOLDEN_RATIO
        self._b = self._GOLDEN_RATIO
        self._c = seed & 0xFF_FF_FF_FF
        # Track bytes processed
        self._length = 0
        # Process data in blocks of 12
        # The remainder is used while digesting
        self._block = bytearray()

    def update(self, data: bytes | bytearray) -> None:
        self._length += len(data)
        self._length &= 0xFF_FF_FF_FF
        l = len(self._block)
        p = 0 # track how far in data we have read
        if l < 12:
            n = 12 - l
            if len(data) < n:
                self._block.extend(data)
                return
            self._block.extend(data[:n])
            p = n
        assert len(self._block) == 12

        while len(self._block) == 12:
            self._a += (self._block[0] + (self._block[ 1] <<  8) + \
                                         (self._block[ 2] << 16) + \
                                         (self._block[ 3] << 24)
                      )
            self._a &= 0xFF_FF_FF_FF

            self._b += (self._block[4] + (self._block[ 5] <<  8) + \
                                         (self._block[ 6] << 16) + \
                                         (self._block[ 7] << 24)
                      )
            self._b &= 0xFF_FF_FF_FF

            self._c += (self._block[8] + (self._block[ 9] <<  8) + \
                                         (self._block[10] << 16) + \
                                         (self._block[11] << 24)
                      )
            self._c &= 0xFF_FF_FF_FF

            self._mix()

            if p >= len(data):
                self._block = bytearray()
                break
            self._block = bytearray(data[p:p + 12])
            p += 12

    def digest(self) -> bytes:
        self._c += self._length
        self._c &= 0xFF_FF_FF_FF
        l = len(self._block)
        if l >= 11:
            self._c += (self._block[10] << 24)
            self._c &= 0xFF_FF_FF_FF
        if l >= 10:
            self._c += (self._block[ 9] << 16)
            self._c &= 0xFF_FF_FF_FF
        if l >= 9:
            self._c += (self._block[ 8] <<  8)
            self._c &= 0xFF_FF_FF_FF
        if l >= 8:
            self._b += (self._block[ 7] << 24)
            self._b &= 0xFF_FF_FF_FF
        if l >= 7:
            self._b += (self._block[ 6] << 16)
            self._b &= 0xFF_FF_FF_FF
        if l >= 6:
            self._b += (self._block[ 5] <<  8)
            self._b &= 0xFF_FF_FF_FF
        if l >= 5:
            self._b += (self._block[ 4] <<  0)
            self._b &= 0xFF_FF_FF_FF
        if l >= 4:
            self._a += (self._block[ 3] << 24)
            self._a &= 0xFF_FF_FF_FF
        if l >= 3:
            self._a += (self._block[ 2] << 16)
            self._a &= 0xFF_FF_FF_FF
        if l >= 2:
            self._a += (self._block[ 1] <<  8)
            self._a &= 0xFF_FF_FF_FF
        if l >= 1:
            self._a += (self._block[ 0] <<  0)
            self._a &= 0xFF_FF_FF_FF
        self._mix()
        return struct.pack(self._fmt, self._c)

    def _mix(self) -> None:
        self._a -= self._b
        self._a -= self._c
        self._a ^= (self._c >> 13)
        self._a &= 0xFF_FF_FF_FF

        self._b -= self._c
        self._b -= self._a
        self._b ^= (self._a <<  8)
        self._b &= 0xFF_FF_FF_FF

        self._c -= self._a
        self._c -= self._b
        self._c ^= (self._b >> 13)
        self._c &= 0xFF_FF_FF_FF

        self._a -= self._b
        self._a -= self._c
        self._a ^= (self._c >> 12)
        self._a &= 0xFF_FF_FF_FF

        self._b -= self._c
        self._b -= self._a
        self._b ^= (self._a << 16)
        self._b &= 0xFF_FF_FF_FF

        self._c -= self._a
        self._c -= self._b
        self._c ^= (self._b >>  5)
        self._c &= 0xFF_FF_FF_FF

        self._a -= self._b
        self._a -= self._c
        self._a ^= (self._c >>  3)
        self._a &= 0xFF_FF_FF_FF

        self._b -= self._c
        self._b -= self._a
        self._b ^= (self._a << 10)
        self._b &= 0xFF_FF_FF_FF

        self._c -= self._a
        self._c -= self._b
        self._c ^= (self._b >> 15)
        self._c &= 0xFF_FF_FF_FF

