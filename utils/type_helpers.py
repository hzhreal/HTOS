import struct
from math import ceil
from enum import Enum
from typing import Literal

class TypeCategory(Enum):
    INTEGER = 1
    CHARACTER = 2
    CHARACTER_SPECIAL = 3

class CIntSignednessState(Enum):
    SIGNED = True
    UNSIGNED = False

class Cint:
    def __init__(self, bits: int, signed: bool, fmt: str, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        if fmt == "":
            fmt_set = (bits, signed)
            fmt_search = self.FMT_TABLE.get(fmt_set)
            if fmt_search is None:
                raise ValueError("No format available.")

            fmt = fmt_search

        self.fmt = self.ENDIANNESS_TABLE[endianness] + fmt
        blen_expected = ceil(bits / 8)
        if struct.calcsize(self.fmt) != blen_expected:
            raise ValueError(f"Format string {self.fmt} does not match expected byte length {blen_expected}!")
        self.ENDIANNESS = endianness

        if signed:
            self.max =  (1 << (bits - 1)) - 1
            self.min = -(1 << (bits - 1))
            self.cast = self.__cast_signed
            self.signedness = CIntSignednessState.SIGNED
        else:
            self.max = (1 << bits) - 1
            self.MIN = 0
            self.cast = self.__cast_unsigned
            self.signedness = CIntSignednessState.UNSIGNED

        match value:
            case int():
                self._value = self.cast(value)
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case str():
                self._value = self.cast(int(value, 16))
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
        self.const = const

    CATEGORY = TypeCategory.INTEGER

    ENDIANNESS_TABLE = {
        "little": "<",
        "big": ">",
        "None": ""
    }

    FMT_TABLE = {
        (8, False): "B", 
        (16, False): "H",
        (32, False): "I",
        (64, False): "Q",
        (8, True): "b",
        (16, True): "h",
        (32, True): "i",
        (64, True): "q"
    }

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: int | str | bytes | bytearray) -> None:
        assert not self.const
        match value:
            case int():
                self._value = self.cast(value)
                self.as_bytes = self.to_bytes()
            case str():
                self._value = self.cast(int(value, 16))
                self.as_bytes = self.to_bytes()
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")

    def to_bytes(self) -> bytes:
        return struct.pack(self.fmt, self._value)

    def from_bytes(self) -> int:
        return struct.unpack(self.fmt, self.as_bytes)[0]

    def __cast_signed(self, n: int) -> int:
        # same as ((n + 2^(b - 1)) mod 2^b) - 2^(b - 1)
        return ((n - self.min) % (-self.min << 1)) + self.min

    def __cast_unsigned(self, n: int) -> int:
        return n & self.max

class uint8(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, const: bool = False) -> None:
        super().__init__(8, False, "B", value, const=const)

class uint16(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(16, False, "H", value, endianness, const)

class uint32(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(32, False, "I", value, endianness, const)

class uint64(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(64, False, "Q", value, endianness, const)

class int8(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, const: bool = False) -> None:
        super().__init__(8, True, "b", value, const=const)

class int16(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(16, True, "h", value, endianness, const)

class int32(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(32, True, "i", value, endianness, const)

class int64(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None", const: bool = False) -> None:
        super().__init__(64, True, "q", value, endianness, const)

class utf_8:
    def __init__(self, value: str | bytes | bytearray = "", const: bool = False) -> None:
        match value:
            case str():
                self._value = value
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
        self.const = const

    CATEGORY = TypeCategory.CHARACTER

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str | bytes | bytearray) -> None:
        assert not self.const
        match value:
            case str():
                self._value = value
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")

    def to_bytes(self) -> bytes:
        return self._value.encode("utf-8")

    def from_bytes(self) -> str:
        return self.as_bytes.decode("utf-8")

class utf_8_s(utf_8):
    def __init__(self, value: str | bytes | bytearray = "", const: bool = False) -> None:
        super().__init__(value, const)

    CATEGORY = TypeCategory.CHARACTER_SPECIAL

    def to_bytes(self) -> bytes:
        return self._value.encode("utf-8", errors="ignore")

    def from_bytes(self) -> str:
        return self.as_bytes.decode("utf-8", errors="ignore")
