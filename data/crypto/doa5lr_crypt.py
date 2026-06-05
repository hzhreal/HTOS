import struct
from dataclasses import dataclass
from typing import Final, ClassVar
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_DoA5LR:
    MAXIMUM_BLOCKS = 100
    @dataclass
    class BlockHeader:
        magic           : int   = 0
        size            : int   = 0
        checksum        : int   = 0
        seed            : int   = 0

        fmt__endianness : ClassVar[Final[str]] = "<"
        fmt__magic      : ClassVar[Final[str]] = "I"
        fmt__size       : ClassVar[Final[str]] = "I"
        fmt__checksum   : ClassVar[Final[str]] = "I"
        fmt__seed       : ClassVar[Final[str]] = "I"

        sizeof__magic   : ClassVar[Final[int]] = struct.calcsize(fmt__magic)
        sizeof__size    : ClassVar[Final[int]] = struct.calcsize(fmt__size)
        sizeof__checksum: ClassVar[Final[int]] = struct.calcsize(fmt__checksum)
        sizeof__seed    : ClassVar[Final[int]] = struct.calcsize(fmt__seed)

        fmt             : ClassVar[Final[str]] = fmt__endianness + fmt__magic + fmt__size + fmt__checksum + fmt__seed
        sizeof__self    : ClassVar[Final[int]] = struct.calcsize(fmt)

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        BlockHeader = Crypt_DoA5LR.BlockHeader
        sizeof_BlockHeader = BlockHeader.sizeof__self
        async with CC(filepath) as cc:
            buf = await cc.ext_read(0, sizeof_BlockHeader)
            bh = BlockHeader(
                *struct.unpack(BlockHeader.fmt, buf)
            )
            p = sizeof_BlockHeader # global offset
            i = sizeof_BlockHeader # chunk offset
            blocks = 0
            if not await cc.read():
                raise CryptoError("Invalid save!")

            while True:
                if bh.size != 0:
                    block_size = bh.size - sizeof_BlockHeader
                else:
                    block_size = cc.size - (p - sizeof_BlockHeader) - sizeof_BlockHeader
                if block_size < 0:
                    raise CryptoError("Invalid save!")

                start = i
                if p + block_size > cc.size:
                    raise CryptoError("Invalid save!")
                elif p + block_size > cc.chunk_end:
                    end = len(cc.chunk)
                    n = block_size - (end - start) # bytes left
                else:
                    end = start + block_size
                    n = 0
                i = end
                p += end - start
                end = end & ~3 # this assumes our chunksize is a multiple of 4

                seed = bh.seed
                for j in range(start, end, 4):
                    cc.chunk[j    ] ^= ((seed      ) & 0xFF)
                    cc.chunk[j + 1] ^= ((seed >>  8) & 0xFF)
                    cc.chunk[j + 2] ^= ((seed >> 16) & 0xFF)
                    cc.chunk[j + 3] ^= ((seed >> 24)       )

                    seed = ((seed << 4) + (seed >> 4)) & 0xFF_FF_FF_FF
                while n != 0:
                    await cc.write()
                    await cc.read()
                    i = 0

                    start = i
                    if p + n > cc.chunk_end:
                        end = len(cc.chunk)
                        n -= (end - start)
                    else:
                        end = start + n
                        n = 0
                    i = end
                    p += end - start
                    end = end & ~3

                    for j in range(start, end, 4):
                        cc.chunk[j    ] ^= ((seed      ) & 0xFF)
                        cc.chunk[j + 1] ^= ((seed >>  8) & 0xFF)
                        cc.chunk[j + 2] ^= ((seed >> 16) & 0xFF)
                        cc.chunk[j + 3] ^= ((seed >> 24)       )

                        seed = ((seed << 4) + (seed >> 4)) & 0xFF_FF_FF_FF

                blocks += 1
                if blocks > Crypt_DoA5LR.MAXIMUM_BLOCKS:
                    raise CryptoError("Unsupported save!")

                # last block
                if bh.size == 0:
                    await cc.write()
                    break

                buf = bytearray(sizeof_BlockHeader)
                if p + sizeof_BlockHeader > cc.chunk_end:
                    n = cc.chunk_end - p
                    if n != 0:
                        buf[:n] = cc.chunk[p:p + n]
                    await cc.write()
                    if not await cc.read():
                        raise CryptoError("Invalid save!")
                    i = 0
                else:
                    n = 0

                if p + sizeof_BlockHeader - n > cc.chunk_end:
                    raise CryptoError("Invalid save!") # or too small chunksize but we assume not
                buf[n:] = cc.chunk[i:i + sizeof_BlockHeader - n]
                bh = BlockHeader(
                    *struct.unpack(BlockHeader.fmt, buf)
                )
                p += sizeof_BlockHeader
                i += sizeof_BlockHeader

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        BlockHeader = Crypt_DoA5LR.BlockHeader
        sizeof_BlockHeader = BlockHeader.sizeof__self
        async with CC(filepath) as cc:
            buf = await cc.ext_read(0, sizeof_BlockHeader)
            bh = BlockHeader(
                *struct.unpack(BlockHeader.fmt, buf)
            )
            p = sizeof_BlockHeader # global offset
            i = sizeof_BlockHeader # chunk offset
            chks_table: list[tuple[int, int]] = [] # (off, chks), max blocks elements
            chks = 0
            chks_off = BlockHeader.sizeof__magic + BlockHeader.sizeof__size
            blocks = 0
            if not await cc.read():
                raise CryptoError("Invalid save!")

            while True:
                if bh.size != 0:
                    block_size = bh.size - sizeof_BlockHeader
                else:
                    block_size = cc.size - (p - sizeof_BlockHeader) - sizeof_BlockHeader
                if block_size < 0:
                    raise CryptoError("Invalid save!")

                start = i
                if p + block_size > cc.size:
                    raise CryptoError("Invalid save!")
                elif p + block_size > cc.chunk_end:
                    end = len(cc.chunk)
                    n = block_size - (end - start) # bytes left
                else:
                    end = start + block_size
                    n = 0
                i = end
                p += end - start
                end = end & ~3 # this assumes our chunksize is a multiple of 4

                seed = bh.seed
                for j in range(start, end, 4):
                    cc.chunk[j    ] ^= ((seed      ) & 0xFF)
                    cc.chunk[j + 1] ^= ((seed >>  8) & 0xFF)
                    cc.chunk[j + 2] ^= ((seed >> 16) & 0xFF)
                    cc.chunk[j + 3] ^= ((seed >> 24)       )

                    chks += cc.chunk[j    ] & 0xFF_FF_FF_FF
                    chks += cc.chunk[j + 1] & 0xFF_FF_FF_FF
                    chks += cc.chunk[j + 2] & 0xFF_FF_FF_FF
                    chks += cc.chunk[j + 3] & 0xFF_FF_FF_FF

                    seed = ((seed << 4) + (seed >> 4)) & 0xFF_FF_FF_FF
                while n != 0:
                    await cc.write()
                    await cc.read()
                    i = 0

                    start = i
                    if p + n > cc.chunk_end:
                        end = len(cc.chunk)
                        n -= (end - start)
                    else:
                        end = start + n
                        n = 0
                    i = end
                    p += end - start
                    end = end & ~3

                    for j in range(start, end, 4):
                        cc.chunk[j    ] ^= ((seed      ) & 0xFF)
                        cc.chunk[j + 1] ^= ((seed >>  8) & 0xFF)
                        cc.chunk[j + 2] ^= ((seed >> 16) & 0xFF)
                        cc.chunk[j + 3] ^= ((seed >> 24)       )

                        chks += cc.chunk[j    ] & 0xFF_FF_FF_FF
                        chks += cc.chunk[j + 1] & 0xFF_FF_FF_FF
                        chks += cc.chunk[j + 2] & 0xFF_FF_FF_FF
                        chks += cc.chunk[j + 3] & 0xFF_FF_FF_FF

                        seed = ((seed << 4) + (seed >> 4)) & 0xFF_FF_FF_FF

                blocks += 1
                if blocks > Crypt_DoA5LR.MAXIMUM_BLOCKS:
                    raise CryptoError("Unsupported save!")
                chks_table.append((chks_off, chks))
                chks = 0
                chks_off = p + BlockHeader.sizeof__magic + BlockHeader.sizeof__size

                # last block
                if bh.size == 0:
                    await cc.write()
                    break

                buf = bytearray(sizeof_BlockHeader)
                if p + sizeof_BlockHeader > cc.chunk_end:
                    n = cc.chunk_end - p
                    if n != 0:
                        buf[:n] = cc.chunk[p:p + n]
                    await cc.write()
                    if not await cc.read():
                        raise CryptoError("Invalid save!")
                    i = 0
                else:
                    n = 0

                if p + sizeof_BlockHeader - n > cc.chunk_end:
                    raise CryptoError("Invalid save!") # or too small chunksize but we assume not
                buf[n:] = cc.chunk[i:i + sizeof_BlockHeader - n]
                bh = BlockHeader(
                    *struct.unpack(BlockHeader.fmt, buf)
                )
                p += sizeof_BlockHeader
                i += sizeof_BlockHeader
            for chks_off, chks in chks_table:
                chks = struct.pack("<I", chks)
                await cc.ext_write(chks_off, chks)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_DoA5LR.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_DoA5LR.encrypt_file(filepath)

