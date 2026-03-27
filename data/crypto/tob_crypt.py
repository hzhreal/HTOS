import struct
from dataclasses import dataclass
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32
from typing import Final, ClassVar

class Crypt_ToB:
    @dataclass
    class ToBEntry:
        item_id : int   = 0
        data_off: int   = 0
        data_len: int   = 0
        flags   : int   = 0
        salt    : bytes = bytes()
        sha1_key: bytes = bytes()

        fmt__endianness: ClassVar[Final[str]] = "<"
        fmt__item_id   : ClassVar[Final[str]] = "I"
        fmt__data_off  : ClassVar[Final[str]] = "I"
        fmt__data_len  : ClassVar[Final[str]] = "I"
        fmt__flags     : ClassVar[Final[str]] = "I"
        fmt__salt      : ClassVar[Final[str]] = "12s"
        fmt__sha1_key  : ClassVar[Final[str]] = "20s"

        sizeof__item_id : ClassVar[Final[int]] = struct.calcsize(fmt__item_id)
        sizeof__data_off: ClassVar[Final[int]] = struct.calcsize(fmt__data_off)
        sizeof__data_len: ClassVar[Final[int]] = struct.calcsize(fmt__data_len)
        sizeof__flags   : ClassVar[Final[int]] = struct.calcsize(fmt__flags)
        sizeof__salt    : ClassVar[Final[int]] = struct.calcsize(fmt__salt)
        sizeof__sha1_key: ClassVar[Final[int]] = struct.calcsize(fmt__sha1_key)

        fmt         : ClassVar[Final[str]] = fmt__endianness + fmt__item_id + fmt__data_off + fmt__data_len + fmt__flags + fmt__salt + fmt__sha1_key
        sizeof__self: ClassVar[Final[int]] = struct.calcsize(fmt)

    MAGIC = 0x64

    HASH_POS       = 0x001C
    HASH_START_POS = 0x0034
    HASH_SALT_POS  = 0x000C
    HASH_SALT_LEN  = 16

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            magic       = uint32(await cc.r_stream.read(4), "little").value
            entry_count = uint32(await cc.r_stream.read(4), "little").value # max 0xFF_FF_FF_FF; no need to add check

            if magic != Crypt_ToB.MAGIC:
                raise CryptoError("Invalid save!")

            for i in range(entry_count):
                buf = await cc.ext_read(Crypt_ToB.ToBEntry.sizeof__self + i * Crypt_ToB.ToBEntry.sizeof__self, Crypt_ToB.ToBEntry.sizeof__self)
                entry = Crypt_ToB.ToBEntry(
                    *struct.unpack(Crypt_ToB.ToBEntry.fmt, buf)
                )

                cc.set_ptr(entry.data_off)
                j = 0
                while await cc.read(stop_off=entry.data_off + entry.data_len):
                    for k in range(len(cc.chunk)):
                        cc.chunk[k] ^= entry.sha1_key[j % entry.sizeof__sha1_key] ^ (j & 0xFF)
                        j += 1
                    await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            magic       = uint32(await cc.r_stream.read(4), "little").value
            entry_count = uint32(await cc.r_stream.read(4), "little").value # max 0xFF_FF_FF_FF; no need to add check
            data_size   = uint32(await cc.r_stream.read(4), "little").value

            await cc.r_stream.seek(Crypt_ToB.HASH_START_POS)
            data_start = uint32(await cc.r_stream.read(4), "little").value

            if magic != Crypt_ToB.MAGIC:
                raise CryptoError("Invalid save!")

            for i in range(entry_count):
                buf = await cc.ext_read(Crypt_ToB.ToBEntry.sizeof__self + i * Crypt_ToB.ToBEntry.sizeof__self, Crypt_ToB.ToBEntry.sizeof__self)
                entry = Crypt_ToB.ToBEntry(
                    *struct.unpack(Crypt_ToB.ToBEntry.fmt, buf)
                )

                cc.set_ptr(entry.data_off)
                j = 0
                while await cc.read(stop_off=entry.data_off + entry.data_len):
                    for k in range(len(cc.chunk)):
                        cc.chunk[k] ^= entry.sha1_key[j % entry.sizeof__sha1_key] ^ (j & 0xFF)
                        j += 1
                    await cc.write()

            sha1 = cc.create_ctx_sha1()
            await cc.checksum(sha1, data_start, data_size)
            salt = await cc.ext_read(Crypt_ToB.HASH_SALT_POS, Crypt_ToB.HASH_SALT_LEN)
            sha1_update_obj = cc._get_ctx(sha1).obj
            sha1_update_obj.update(salt)
            await cc.write_checksum(sha1, Crypt_ToB.HASH_POS)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_ToB.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            is_dec = await cc.fraction_byte()
        if is_dec:
            await Crypt_ToB.encrypt_file(filepath)

