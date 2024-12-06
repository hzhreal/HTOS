import struct
from math import ceil
from enum import Enum
from typing import Literal

class TypeCategory(Enum):
    INTEGER = 1
    CHARACTER = 2
    CHARACTER_SPECIAL = 3

class Cint:
    def __init__(self, bits: int, signed: bool, fmt: str, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        self.fmt = self.FMT_TABLE[endianness] + fmt
        blen_expected = ceil(bits / 8)
        if struct.calcsize(self.fmt) != blen_expected:
            raise ValueError(f"Format string {self.fmt} does not match expected byte length {blen_expected}!")
        
        if signed:
            self.max =  (1 << (bits - 1)) - 1
            self.min = -(1 << (bits - 1))
            self.cast = self.__cast_signed
        else:
            self.max = (1 << bits) - 1
            self.MIN = 0
            self.cast = self.__cast_unsigned

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
            
    CATEGORY = TypeCategory.INTEGER

    FMT_TABLE = {
        "little": "<",
        "big": ">",
        "None": ""
    }

    @property
    def value(self) -> int:
        return self._value
    
    @value.setter
    def value(self, value: int | str | bytes | bytearray) -> None:
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
    
    def change_endianness(self, endianness: Literal["little", "big", "None"]) -> None:
        self.fmt[0] = self.FMT_TABLE[endianness]
    
    def __cast_signed(self, n: int) -> int:
        # same as ((n + 2^(b - 1)) mod 2^b) - 2^(b - 1)
        return ((n - self.min) % (-self.min << 1)) + self.min
    
    def __cast_unsigned(self, n: int) -> int:
        return n & self.max
    
class uint8(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0) -> None:
        super().__init__(8, False, "B", value)

class uint16(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(16, False, "H", value, endianness)
    
class uint32(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(32, False, "I", value, endianness)

class uint64(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(64, False, "Q", value, endianness)

class int8(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0) -> None:
        super().__init__(8, True, "b", value)

class int16(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(16, True, "h", value, endianness)
    
class int32(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(32, True, "i", value, endianness)

class int64(Cint):
    def __init__(self, value: int | str | bytes | bytearray = 0, endianness: Literal["little", "big", "None"] = "None") -> None:
        super().__init__(64, True, "q", value, endianness)

class utf_8:
    def __init__(self, value: str | bytes | bytearray = "") -> None:
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
    
    CATEGORY = TypeCategory.CHARACTER

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str | bytes | bytearray) -> None:
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
    def __init__(self, value: str | bytes | bytearray = "") -> None:
        super().__init__(value)

    CATEGORY = TypeCategory.CHARACTER_SPECIAL
    
    def to_bytes(self) -> bytes:
        return self._value.encode("utf-8", errors="ignore")
    
    def from_bytes(self) -> str:
        return self.as_bytes.decode("utf-8", errors="ignore")