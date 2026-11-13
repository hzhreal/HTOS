from __future__ import annotations

import datetime
import struct
from dataclasses import dataclass, astuple
from enum import Enum
from typing import ClassVar, Final

from utils.constants import SYS_FILE_MAX
from utils.type_helpers import uint32, uint64, utf_8, bytestr
from utils.exceptions import OrbisError

SFO_MAGIC = 0x46535000
SFO_VERSION = 0x0101

@dataclass
class SFOHeader:
    magic                 : int
    version               : int
    key_table_offset      : int
    data_table_offset     : int
    num_entries           : int

    fmt__endianness       : ClassVar[Final[str]] = "<"
    fmt__magic            : ClassVar[Final[str]] = "I"
    fmt__version          : ClassVar[Final[str]] = "I"
    fmt__key_table_offset : ClassVar[Final[str]] = "I"
    fmt__data_table_offset: ClassVar[Final[str]] = "I"
    fmt__num_entries      : ClassVar[Final[str]] = "I"

    fmt                   : ClassVar[Final[str]] = fmt__endianness + \
                                                   fmt__magic + \
                                                   fmt__version + \
                                                   fmt__key_table_offset + \
                                                   fmt__data_table_offset + \
                                                   fmt__num_entries
    sizeof__self          : ClassVar[Final[int]] = struct.calcsize(fmt)

@dataclass
class SFOIndexTable:
    key_offset           : int
    param_format         : int
    param_length         : int
    param_max_length     : int
    data_offset          : int

    fmt__endianness      : ClassVar[Final[str]] = "<"
    fmt__key_offset      : ClassVar[Final[str]] = "H"
    fmt__param_format    : ClassVar[Final[str]] = "H"
    fmt__param_length    : ClassVar[Final[str]] = "I"
    fmt__param_max_length: ClassVar[Final[str]] = "I"
    fmt__data_offset     : ClassVar[Final[str]] = "I"

    fmt                  : ClassVar[Final[str]] = fmt__endianness + \
                                                  fmt__key_offset + \
                                                  fmt__param_format + \
                                                  fmt__param_length + \
                                                  fmt__param_max_length + \
                                                  fmt__data_offset
    sizeof__self         : ClassVar[Final[int]] = struct.calcsize(fmt)

class SFOParamFormat(Enum):
    BINARY  = 0x0004
    UTF8    = 0x0204
    INTEGER = 0x0404

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def get_self(n: int) -> SFOParamFormat | None:
        if n in SFOParamFormat:
            return SFOParamFormat(n)
        return None

# account_id: uint64
# attribute: uint32
# category: utf-8
# detail: utf-8
# format: utf-8
# maintitle: utf-8
# params: struct
# savedata_blocks: uint64
# savedata_directory: utf-8
# savedata_list_param: uint32
# subtitle: utf-8
# title_id: utf-8

@dataclass
class SFOParamPARAMS:
    version                : int
    user_id                : int
    openpsid_hmac          : bytes
    counter_index          : int
    title_id_1             : bytes
    title_id_2             : bytes
    counter_retail_1       : int
    counter_testkit_2      : int
    counter_devkit_3       : int
    fake_owner_flag        : int
    flags                  : int
    creation_time          : int
    last_modified_time     : int
    corrupt_flag           : int

    fmt__endianness        : ClassVar[Final[str]] = "<"
    fmt__version           : ClassVar[Final[str]] = "I"
    fmt__user_id           : ClassVar[Final[str]] = "I"
    fmt__openpsid_hmac     : ClassVar[Final[str]] = "32s"
    fmt__counter_index     : ClassVar[Final[str]] = "I"
    fmt__title_id_1        : ClassVar[Final[str]] = "16s"
    fmt__title_id_2        : ClassVar[Final[str]] = "16s"
    fmt__counter_1         : ClassVar[Final[str]] = "I"
    fmt__counter_2         : ClassVar[Final[str]] = "I"
    fmt__counter_3         : ClassVar[Final[str]] = "I"
    fmt__fake_owner_flag   : ClassVar[Final[str]] = "I"
    fmt__flags             : ClassVar[Final[str]] = "I"
    fmt__creation_time     : ClassVar[Final[str]] = "Q"
    fmt__last_modified_time: ClassVar[Final[str]] = "Q"
    fmt__corrupt_flag      : ClassVar[Final[str]] = "I"

    fmt                    : ClassVar[Final[str]] = fmt__endianness + \
                                                    fmt__version + \
                                                    fmt__user_id + \
                                                    fmt__openpsid_hmac + \
                                                    fmt__counter_index + \
                                                    fmt__title_id_1 + \
                                                    fmt__title_id_2 + \
                                                    fmt__counter_1 + \
                                                    fmt__counter_2 + \
                                                    fmt__counter_3 + \
                                                    fmt__fake_owner_flag + \
                                                    fmt__flags + \
                                                    fmt__creation_time + \
                                                    fmt__last_modified_time + \
                                                    fmt__corrupt_flag
    sizeof__self           : ClassVar[Final[int]] = struct.calcsize(fmt)

    def __str__(self) -> str:
        try:
            creation_time = str(datetime.datetime.fromtimestamp(
                self.creation_time, datetime.timezone.utc
            ))
        except:
            creation_time = self.creation_time
        try:
            last_modified_time = str(datetime.datetime.fromtimestamp(
                self.last_modified_time, datetime.timezone.utc
            ))
        except:
            last_modified_time = self.last_modified_time

        return (
            f"\nversion={self.version}\n"
            f"user_id={hex(self.user_id)[2:]}\n"
            f"openpsid_hmac={self.openpsid_hmac.hex()}\n"
            f"title_id_1={self.title_id_1.decode("ascii", "ignore").rstrip("\x00")}\n"
            f"title_id_2={self.title_id_2.decode("ascii", "ignore").rstrip("\x00")}\n"
            f"counter_retail_1={self.counter_retail_1}\n"
            f"counter_testkit_2={self.counter_testkit_2}\n"
            f"counter_devkit_3={self.counter_devkit_3}\n"
            f"fake_owner_flag={bool(self.fake_owner_flag)}\n"
            f"flags={hex(self.flags)}\n"
            f"creation_time={creation_time}\n"
            f"last_modified_time={last_modified_time}\n"
            f"corrupt_flag={bool(self.corrupt_flag)}"
        )

@dataclass
class SFOParam:
    key: str
    format: SFOParamFormat
    length: int
    max_length: int
    value: bytearray

    def set_value(self, new_data: str | int) -> None:
        match self.format:
            case SFOParamFormat.BINARY:
                if self.key in ("ACCOUNT_ID", "SAVEDATA_BLOCKS"):
                    v = uint64(new_data, "little").as_bytes
                else:
                    assert isinstance(new_data, str)
                    v = bytestr(new_data).as_bytes
            case SFOParamFormat.UTF8:
                assert isinstance(new_data, str)
                v = utf_8(new_data).to_cstr()
            case SFOParamFormat.INTEGER:
                v = uint32(new_data, "little").as_bytes

        if self.key == "PARAMS":
            l = 1024
        else:
            l = len(v)
        if l > self.max_length:
            raise OrbisError(f"The parameter: {key} reached the max length it has of {self.max_length}!")
        if self.format == SFOParamFormat.UTF8 and l == self.max_length:
            l -= 1
        self.length = l
        self.value = bytearray(v)

    def get_value(self) -> str | int:
        match self.format:
            case SFOParamFormat.BINARY:
                if self.key in ("ACCOUNT_ID", "SAVEDATA_BLOCKS"):
                    v = uint64(self.value, "little").value
                else:
                    v = bytestr(self.value).as_bytes.rstrip(b"\x00").hex()
            case SFOParamFormat.UTF8:
                v = utf_8(self.value).to_str()
            case SFOParamFormat.INTEGER:
                v = uint32(self.value, "little").value

        return v

    def as_dict(self) -> dict[str, str | int | bytearray]:
        info = {k: str(v) for k, v in vars(self).items()}
        value = self.get_value()

        if self.key == "ACCOUNT_ID":
            value = hex(value)[2:].zfill(16)
        if self.format == SFOParamFormat.INTEGER:
            value = hex(value)
        if self.key == "PARAMS" and self.length >= SFOParamPARAMS.sizeof__self:
            p = SFOParamPARAMS(
                *struct.unpack(SFOParamPARAMS.fmt, self.value[:SFOParamPARAMS.sizeof__self])
            )
            info["struct"] = str(p)

        info["value"] = str(value)

        return info

class SFOContext:
    def __init__(self) -> None:
        self.params: dict[str, SFOParam] = {}

    def read(self, sfo: bytearray) -> None:
        sfo_len = len(sfo)
        i = 0

        if i + SFOHeader.sizeof__self > sfo_len:
            raise OrbisError("Invalid param.sfo!")
        header = SFOHeader(
            *struct.unpack(SFOHeader.fmt, sfo[i:i + SFOHeader.sizeof__self])
        )
        i += SFOHeader.sizeof__self
        if header.magic != SFO_MAGIC:
            raise OrbisError("Invalid param.sfo header magic!")
        if header.num_entries > 12:
            raise OrbisError("The param.sfo has too many entries!")

        end = i + SFOIndexTable.sizeof__self * header.num_entries
        if end > sfo_len:
            raise OrbisError("Invalid param.sfo!")
        total_entry_sizes = 0
        for i in range(i, end, SFOIndexTable.sizeof__self):
            index_table = SFOIndexTable(
                *struct.unpack(SFOIndexTable.fmt, sfo[i:i + SFOIndexTable.sizeof__self])
            )
            if index_table.param_length > index_table.param_max_length:
                raise OrbisError("Invalid param.sfo!")
            param_format = SFOParamFormat.get_self(index_table.param_format)
            if param_format is None:
                raise OrbisError("Invalid param.sfo!")

            param_offset = header.key_table_offset + index_table.key_offset
            key_end = sfo.find(b"\x00", param_offset)
            if key_end == -1 or param_offset > key_end or key_end > sfo_len:
                raise OrbisError("Invalid param.sfo!")
            try:
                param_key = sfo[param_offset:key_end].decode(encoding="ascii")
            except UnicodeDecodeError:
                raise OrbisError("Invalid param.sfo!")
            if param_key in self.params:
                raise OrbisError("Invalid param.sfo!")

            param_data_offset = header.data_table_offset + index_table.data_offset
            if param_data_offset + index_table.param_max_length > sfo_len:
                raise OrbisError("Invalid param.sfo!")
            total_entry_sizes += index_table.param_max_length
            if total_entry_sizes > sfo_len:
                raise OrbisError("Invalid param.sfo!")
            param_value = sfo[param_data_offset:param_data_offset + index_table.param_length]

            param = SFOParam(
                key=param_key,
                format=param_format,
                length=index_table.param_length,
                max_length=index_table.param_max_length,
                value=param_value
            )
            self.params[param_key] = param

    def write(self) -> bytearray:
        num_entries = len(self.params)
        key_table_size = 0
        data_table_size = 0

        for param in self.params.values():
            key_table_size += len(param.key) + 1
            data_table_size += param.max_length
        r = key_table_size % 4
        if r != 0:
            key_table_size = key_table_size + (4 - r)
        key_table_offset = SFOHeader.sizeof__self + SFOIndexTable.sizeof__self * num_entries
        data_table_offset = key_table_offset + key_table_size

        sfo_size = data_table_offset + data_table_size
        assert sfo_size <= SYS_FILE_MAX
        sfo = bytearray(sfo_size)

        header = SFOHeader(
            magic=SFO_MAGIC,
            version=SFO_VERSION,
            key_table_offset=key_table_offset,
            data_table_offset=data_table_offset,
            num_entries=num_entries
        )

        i = 0
        try:
            struct.pack_into(
                SFOHeader.fmt,
                sfo, i,
                *astuple(header)
            )
        except struct.error:
            assert 0
        i += SFOHeader.sizeof__self

        end = i + SFOIndexTable.sizeof__self * num_entries
        key_offset = 0
        data_offset = 0
        for i, param in zip( range(i, end, SFOIndexTable.sizeof__self), sorted(self.params.values(), key=lambda v: v.key) ):
            index_table = SFOIndexTable(
                key_offset=key_offset,
                param_format=param.format.value,
                param_length=param.length,
                param_max_length=param.max_length,
                data_offset=data_offset
            )

            try:
                struct.pack_into(
                    SFOIndexTable.fmt,
                    sfo, i,
                    *astuple(index_table)
                )
            except struct.error:
                assert 0

            l = len(param.key)
            base = header.key_table_offset + key_offset
            sfo[base:base + l] = param.key.encode(encoding="ascii")
            key_offset += l + 1

            l = len(param.value)
            assert l <= param.max_length
            base = header.data_table_offset + data_offset
            sfo[base:base + l] = param.value
            data_offset += param.max_length

        return sfo

    def patch_parameter(self, parameter: str, new_data: str | int) -> None:
        param = self.params.get(parameter)
        if param is None:
            raise OrbisError(f"Invalid parameter: {parameter}!")
        param.set_value(new_data)

    def get_param_value(self, parameter: str) -> str | int:
        param = self.params.get(parameter)
        if param is None:
            raise OrbisError(f"Missing sfo parameter: {parameter}!")
        return param.get_value()

    def get_param_data(self) -> list[dict[str, str | int | bytearray]]:
        param_data = []
        for param in sorted(self.params.values(), key=lambda v: v.key):
            try:
                param_data.append(param.as_dict())
            except ValueError:
                raise OrbisError("Failed to get param data!")
        return param_data

