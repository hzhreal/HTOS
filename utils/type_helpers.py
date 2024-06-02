import struct
from typing import Literal

fmt = {
    "little": "<",
    "big": ">"
}

INTEGER = 0
CHARACTER = 1
CHARACTER_SPECIAL = 11

class uint32:
    def __init__(self, value: int | str | bytes | bytearray, endianness: Literal["little", "big"]) -> None:
        self.fmt = fmt[endianness] + "I"

        match value:
            case int():
                self._value = value & 0xFF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case str():
                self._value = int(value, 16) & 0xFF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                assert self.bytelen == 4
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
            
    CATEGORY = INTEGER

    @property
    def value(self) -> int:
        return self._value
    
    @value.setter
    def value(self, value: int | str | bytes | bytearray) -> None:
        match value:
            case int():
                self._value = value & 0xFF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                # bytelen will always be the same
            case str():
                self._value = int(value, 16) & 0xFF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                # bytelen will always be the same
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                assert self.bytelen == 4
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
    
    def to_bytes(self) -> bytes:
        return struct.pack(self.fmt, self._value)
    
    def from_bytes(self) -> int:
        return struct.unpack(self.fmt, self.as_bytes)[0]
    
class uint64:
    def __init__(self, value: int | bytes | bytearray, endianness: Literal["little", "big"]) -> None:
        self.fmt = fmt[endianness] + "Q"
        
        match value:
            case int():
                self._value = value & 0xFF_FF_FF_FF_FF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case str():
                self._value = int(value, 16) & 0xFF_FF_FF_FF_FF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                self.bytelen = len(self.as_bytes)
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                assert self.bytelen == 8
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
            
    CATEGORY = INTEGER

    @property
    def value(self) -> int:
        return self._value
    
    @value.setter
    def value(self, value: int | bytes | bytearray) -> None:
        match value:
            case int():
                self._value = value & 0xFF_FF_FF_FF_FF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                # bytelen will always be the same
            case str():
                self._value = int(value, 16) & 0xFF_FF_FF_FF_FF_FF_FF_FF
                self.as_bytes = self.to_bytes()
                # bytelen will always be the same
            case bytes() | bytearray():
                self.as_bytes = bytes(value)
                self.bytelen = len(self.as_bytes)
                assert self.bytelen == 8
                self._value = self.from_bytes()
            case _:
                raise ValueError("Invalid type!")
    
    def to_bytes(self) -> bytes:
        return struct.pack(self.fmt, self._value)

    def from_bytes(self) -> int:
        return struct.unpack(self.fmt, self.as_bytes)[0]
    
class utf_8:
    def __init__(self, value: str | bytes | bytearray) -> None:
        if isinstance(value, str):
            self._value = value
            self.as_bytes = self.to_bytes()
            self.bytelen = len(self.as_bytes)
        else:
            self.as_bytes = bytes(value)
            self.bytelen = len(self.as_bytes)
            self._value = self.from_bytes()
    
    CATEGORY = CHARACTER

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: str | bytes | bytearray) -> None:
        if isinstance(value, str):
            self._value = value
            self.as_bytes = self.to_bytes()
            self.bytelen = len(self.as_bytes)
        else:
            self.as_bytes = bytes(value)
            self.bytelen = len(self.as_bytes)
            self._value = self.from_bytes()
    
    def to_bytes(self) -> bytes:
        return self._value.encode("utf-8")
    
    def from_bytes(self) -> str:
        return self.as_bytes.decode("utf-8")

class utf_8_s(utf_8):
    def __init__(self, value: str | bytes | bytearray) -> None:
        super().__init__(value)

    CATEGORY = CHARACTER_SPECIAL
    
    def to_bytes(self) -> bytes:
        return self._value.encode("utf-8", errors="ignore")
    
    def from_bytes(self) -> str:
        return self.as_bytes.decode("utf-8", errors="ignore")