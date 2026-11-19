import struct
from typing import Sequence, Literal

S = (
    7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,
    5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,
    4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,
    6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21
)

# K[i] = floor( 2^32 * abs(sin(i + 1)) ) for i = 0, ..., 63
K = (
    0xD76AA478, 0xE8C7B756, 0x242070DB, 0xC1BDCEEE,
    0xF57C0FAF, 0x4787C62A, 0xA8304613, 0xFD469501,
    0x698098D8, 0x8B44F7AF, 0xFFFF5BB1, 0x895CD7BE,
    0x6B901122, 0xFD987193, 0xA679438E, 0x49B40821,
    0xF61E2562, 0xC040B340, 0x265E5A51, 0xE9B6C7AA,
    0xD62F105D, 0x02441453, 0xD8A1E681, 0xE7D3FBC8,
    0x21E1CDE6, 0xC33707D6, 0xF4D50D87, 0x455A14ED,
    0xA9E3E905, 0xFCEFA3F8, 0x676F02D9, 0x8D2A4C8A,
    0xFFFA3942, 0x8771F681, 0x6D9D6122, 0xFDE5380C,
    0xA4BEEA44, 0x4BDECFA9, 0xF6BB4B60, 0xBEBFBC70,
    0x289B7EC6, 0xEAA127FA, 0xD4EF3085, 0x04881D05,
    0xD9D4D039, 0xE6DB99E5, 0x1FA27CF8, 0xC4AC5665,
    0xF4292244, 0x432AFF97, 0xAB9423A7, 0xFC93A039,
    0x655B59C3, 0x8F0CCC92, 0xFFEFF47D, 0x85845DD1,
    0x6FA87E4F, 0xFE2CE6E0, 0xA3014314, 0x4E0811A1,
    0xF7537E82, 0xBD3AF235, 0x2AD7D2BB, 0xEB86D391
)

A0 = 0x67452301
B0 = 0xEFCDAB89
C0 = 0x98BADCFE
D0 = 0x10325476

class MD5:
    def __init__(
        self,
        S: Sequence[int] = S,
        K: Sequence[int] = K,
        A0: int = A0,
        B0: int = B0,
        C0: int = C0,
        D0: int = D0,
        MASK: int = 0xFF_FF_FF_FF,
        endianness: Literal["little", "big", "None"] = "little",
        data: bytes | bytearray | None = None
    ) -> None:
        self._S = S
        self._K = K
        self._a0 = A0
        self._b0 = B0
        self._c0 = C0
        self._d0 = D0
        self._MASK = MASK
        self._fmt = {
            "little": "<",
            "big"   : ">",
            "None"  : ""
        }[endianness]

        self._chunk = bytearray()
        self._length = 0

        if data is not None:
            self.update(data)

    def _process(self) -> None:
        S = self._S
        K = self._K
        M = self._MASK
        fmt = self._fmt
        chunk = self._chunk

        while len(chunk) >= 64:
            m = struct.unpack(fmt + "16I", chunk[:64])
            del chunk[:64]

            a = self._a0
            b = self._b0
            c = self._c0
            d = self._d0

            for i in range(64):
                if i <= 15:
                    f = (b & c) | ((b ^ M) & d)
                    g = i
                elif i <= 31:
                    f = (d & b) | ((d ^ M) & c)
                    g = (5 * i + 1) & 0xF # % 16
                elif i <= 47:
                    f = b ^ c ^ d
                    g = (3 * i + 5) & 0xF
                else:
                    f = c ^ (b | (d ^ M))
                    g = (7 * i) & 0xF
                f = (f + a + K[i] + m[g]) & M
                a = d
                d = c
                c = b
                rotf = ( (f << S[i]) | (f >> (32 - S[i])) ) & M
                b = (b + rotf) & M

            self._a0 = (self._a0 + a) & M
            self._b0 = (self._b0 + b) & M
            self._c0 = (self._c0 + c) & M
            self._d0 = (self._d0 + d) & M

    def update(self, data: bytes | bytearray) -> None:
        self._chunk.extend(data)
        self._length = (self._length + len(data) * 8) & 0xFF_FF_FF_FF_FF_FF_FF_FF

        self._process()

    def digest(self) -> None:
        # we do the pre-processing part now since we are at the end of the stream
        self._chunk.append(0b10000000)
        r = len(self._chunk) & 0x3F # % 64
        if r > 56:
            p = (64 - r) + 56
        else :
            p = 56 - r
        self._chunk.extend(bytes(p))
        self._chunk.extend(struct.pack(self._fmt + "Q", self._length))

        self._process()
        return struct.pack(
            self._fmt + "4I",
            self._a0 & 0xFF_FF_FF_FF,
            self._b0 & 0xFF_FF_FF_FF,
            self._c0 & 0xFF_FF_FF_FF,
            self._d0 & 0xFF_FF_FF_FF
        )

