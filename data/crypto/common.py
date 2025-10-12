import os
import aiofiles.os

from enum import Enum
from aiofiles.threadpool.binary import AsyncBufferedReader
from Crypto.Cipher import AES, Blowfish
from typing import Literal

from utils.constants import SCE_SYS_NAME
from utils.conversions import mb_to_bytes
from utils.type_helpers import uint8, uint32

class CustomCryptoType(Enum):
    AES = AES.block_size
    BLOWFISH = Blowfish.block_size
    OTHER = -1

class CustomCrypto:
    DEFAULT_CHUNKSIZE = mb_to_bytes(1)

    def __init__(
        self,
        stream: AsyncBufferedReader,
        blocksize: CustomCryptoType | int
    ) -> None:
        self.stream = stream
        self.set_type(blocksize)
        self.chunk = None
        self.size = None
        self.chunk_start = 0
        self.chunk_end = 0
        self.cipher = None

    def set_type(self, t: CustomCryptoType | int) -> None:
        if isinstance(t, CustomCryptoType):
            self.blocksize = t.value
        else:
            assert type(t) == int and t > 0
            self.blocksize = t

        if self.blocksize != -1:
            self.chunksize = self.DEFAULT_CHUNKSIZE & ~(self.blocksize - 1)
        else:
            self.chunksize = self.DEFAULT_CHUNKSIZE

    def set_ptr(self, p: int) -> None:
        self.chunk_end = p
        self.chunk_start = -1

    async def get_size(self) -> None:
        self.size = await self.stream.seek(0, 2)

    async def read(self) -> None:
        self.chunk_start = await self.stream.seek(self.chunk_end)
        self.chunk = bytearray(await self.stream.read(self.chunksize))
        self.chunk_end = await self.stream.tell()

    async def write(self) -> None:
        assert type(self.chunk) == bytearray
        await self.stream.seek(self.chunk_start)
        await self.stream.write(self.chunk)

    async def truncate_to_blocksize(self) -> None:
        assert self.blocksize != -1
        if self.size is None:
            await self.get_size()

        self.size = self.size & ~(self.blocksize - 1)
        await self.stream.truncate(self.size)
    
    async def pad_to_blocksize(self) -> None:
        assert self.blocksize != -1
        if self.size is None:
            await self.get_size()
        
        pad_len = uint8(self.blocksize - (self.size % self.blocksize))
        
        await self.stream.seek(0, 2)
        await self.stream.write(pad_len.as_bytes * pad_len.value)

    async def remove_padding(self) -> None:
        assert self.blocksize != -1
        if self.size is None:
            await self.get_size()
        
        await self.stream.seek(-1, 2)
        p = (await self.stream.read(1))[0]
        if not (1 <= p <= self.blocksize):
            return
        self.size = await self.stream.truncate(self.size - p)

    async def trim_trailing_bytes(self, off: int, byte: uint8 = uint8(0)) -> None:
        """Start from off and move backward, stop when a byte that differs from the given has been reached. Truncate data from the occurence offset."""
        assert 0 <= off < self.size
        if self.size is None:
            await self.get_size()

        pos = off + 1
        stop_off = -1

        while pos > 0:
            read_size = min(pos, self.chunksize)
            await self.stream.seek(pos - read_size)
            chunk = await self.stream.read(read_size)
            chunksize = len(chunk)

            for i in range(chunksize - 1, -1, -1):
                if chunk[i] != byte.value:
                    stop_off = pos - read_size + i
                    break
            if stop_off != -1:
                break
            pos -= read_size

        if stop_off == -1:
            return
        self.size = await self.stream.truncate(stop_off + 1)

    def bytes_to_u32array(self, byteorder: Literal["little", "big"]) -> None:
        assert type(self.chunk) == bytearray
        assert self.blocksize % 4 == 0
        if not self.chunk:
            return

        u32_array = []
        for i in range(0, len(self.chunk), 4):
            u32 = uint32(self.chunk[i:i + 4], endianness=byteorder)
            u32_array.append(u32)
        self.chunk = u32_array
    
    def array_to_bytearray(self) -> None:
        assert type(self.chunk) == list
        new_array = bytearray()
        for u in self.chunk:
            u: uint32
            new_array.extend(u.as_bytes)
        self.chunk = new_array
    
    def ES32(self) -> None:
        assert type(self.chunk) == bytearray

        for i in range(0, len(self.chunk), 4):
            self.chunk[i:i + 4] = self.chunk[i:i + 4][::-1]

    async def fraction_byte(self, byte: uint8 = uint8(0), div: int = 2) -> bool:
        assert div != 0
        if self.size is None:
            await self.get_size()
        
        await self.stream.seek(0)
        cnt = 0
        while True:
            chunk = await self.stream.read(self.chunksize)
            if not chunk:
                break

            cnt += chunk.count(byte.value)
            if cnt * div >= self.size:
                return True
        return cnt * div >= self.size
    
    def encrypt(self) -> None:
        assert self.cipher is not None
        assert type(self.chunk) == bytearray
        self.cipher.encrypt(self.chunk)
    
    def decrypt(self) -> None:
        assert self.cipher is not None
        assert type(self.chunk) == bytearray
        self.cipher.decrypt(self.chunk)
    
    def create_aes_ecb(self, key: bytes | bytearray) -> None:
        assert self.blocksize == CustomCryptoType.AES.value
        self.cipher = AES.new(key, AES.MODE_ECB)

    def create_aes_cbc(self, key: bytes | bytearray, iv: bytes | bytearray) -> None:
        assert self.blocksize == CustomCryptoType.AES.value
        self.cipher = AES.new(key, AES.MODE_CBC, iv)

    def create_blowfish_ecb(self, key: bytes | bytearray) -> None:
        assert self.blocksize == CustomCryptoType.BLOWFISH.value
        self.cipher = Blowfish.new(key, Blowfish.MODE_ECB)

    def create_blowfish_cbc(self, key: bytes | bytearray, iv: bytes | bytearray) -> None:
        assert self.blocksize == CustomCryptoType.BLOWFISH.value
        self.cipher = Blowfish.new(key, Blowfish.MODE_CBC, iv)

    @staticmethod
    async def obtainFiles(path: str, exclude: list[str] | None = None, files: list[str] | None = None) -> list[str]:
        if exclude is None:
            exclude = []
        if files is None:
            # first run so check if a file is given
            if await aiofiles.os.path.isfile(path):
                basename = os.path.basename(path)
                if basename in exclude:
                    return []
                else:
                    return [path]
            files = []

        filelist = await aiofiles.os.listdir(path)

        for entry in filelist:
            entry_path = os.path.join(path, entry)

            if await aiofiles.os.path.isfile(entry_path) and entry not in exclude:
                files.append(entry_path)
            elif await aiofiles.os.path.isdir(entry_path) and entry_path != os.path.join(path, SCE_SYS_NAME):
                await CustomCrypto.obtainFiles(entry_path, exclude, files)

        return files