import os
import hashlib
import aiofiles
import aiofiles.os
import crc32c
import mmh3
import zlib
import pyzstd

from data.crypto.exceptions import CryptoError

from aiofiles.threadpool.binary import AsyncBufferedReader
from Crypto.Cipher import AES, Blowfish
from typing import Literal, Any, Self
from functools import partial

from utils.constants import SCE_SYS_NAME, RANDOMSTRING_LENGTH, SAVESIZE_MAX
from utils.conversions import mb_to_bytes
from utils.type_helpers import Cint, uint8, uint32
from utils.extras import generate_random_string

class CustomCryptoCtx:
    def __init__(
        self,
        obj: Any,
        attr: Any | None = None
    ) -> None:
        self.obj = obj
        self.attr = attr

class CustomCrypto:
    CHUNKSIZE = mb_to_bytes(1)
    AES = AES
    Blowfish = Blowfish
    zlib = zlib
    zstd = pyzstd
    crc32c = crc32c
    mmh3 = mmh3
    hashlib = hashlib

    def __init__(
        self,
        filepath: str,
        in_place: bool = True
    ) -> None:
        self.filepath = filepath
        self.temp_filepath = None
        self.in_place = in_place
        self.r_stream: AsyncBufferedReader | None = None
        self.w_stream: AsyncBufferedReader | None = None

        self.chunk = None
        self.size = None
        self.chunk_start = 0
        self.chunk_end = 0

        self.ctx_container: dict[int, CustomCryptoCtx] = {}
        self.i = 0

    async def __aenter__(self) -> Self:
        self.r_stream = await aiofiles.open(self.filepath, "r+b")

        if self.in_place:
            self.w_stream = self.r_stream
        else:
            rand_str = generate_random_string(RANDOMSTRING_LENGTH)
            self.temp_filepath = os.path.join(os.path.dirname(self.filepath), rand_str)
            self.w_stream = await aiofiles.open(self.temp_filepath, "w+b")
        return self

    async def __aexit__(self) -> None:
        await self.r_stream.close()
        if self.r_stream is not self.w_stream:
            await self.w_stream.close()
            await aiofiles.os.replace(self.temp_filepath, self.filepath)

    def set_ptr(self, p: int) -> None:
        self.chunk_end = p
        self.chunk_start = -1

    async def get_size(self) -> None:
        self.size = await self.r_stream.seek(0, 2)

    async def read(self) -> int:
        self.chunk_start = await self.r_stream.seek(self.chunk_end)
        self.chunk = bytearray(await self.r_stream.read(self.CHUNKSIZE))
        self.chunk_end = await self.r_stream.tell()
        return len(self.chunk)

    async def write(self) -> int:
        self._prepare_write()
        await self.w_stream.seek(self.chunk_start)
        return await self.w_stream.write(self.chunk)

    def _get_ctx(self, ctx: int) -> CustomCryptoCtx:
        assert ctx in self.ctx_container
        return self.ctx_container[ctx]

    def delete_ctx(self, ctx: int) -> None:
        self._get_ctx(ctx)
        del self.ctx_container[ctx]

    def _prepare_write(self) -> None:
        assert type(self.chunk) == bytearray

    def _prepare_compression(self) -> None:
        assert not self.in_place

    async def trim_trailing_bytes(self, off: int, byte: uint8 = uint8(0)) -> None:
        """Start from off and move backward, stop when a byte that differs from the given has been reached. Truncate data from the occurence offset."""
        assert 0 <= off < self.size
        if self.size is None:
            await self.get_size()

        pos = off + 1
        stop_off = -1

        while pos > 0:
            r_len = min(pos, self.CHUNKSIZE)
            await self.r_stream.seek(pos - r_len)
            chunk = await self.r_stream.read(r_len)
            chunksize = len(chunk)

            for i in range(chunksize - 1, -1, -1):
                if chunk[i] != byte.value:
                    stop_off = pos - r_len + i
                    break
            if stop_off != -1:
                break
            pos -= r_len

        if stop_off == -1:
            return
        self.size = await self.r_stream.truncate(stop_off + 1)

    async def find(self, d: bytes | bytearray, start_off: int = 0, end_off: int = -1) -> int:
        if end_off < 0:
            if self.size is None:
                self.get_size()
            end_off = self.size
        assert start_off < end_off

        d_len = len(d)
        assert d_len <= self.CHUNKSIZE # bound growth
        target_off = -1
        buf = bytes()
        await self.r_stream.seek(start_off)

        for off in range(start_off, end_off, self.CHUNKSIZE):
            r_len = min(self.CHUNKSIZE, end_off - off)
            chunk = await self.r_stream.read(r_len)
            if not chunk:
                break
            chunk = buf + chunk
            chunk_len = len(chunk)

            if (pos := chunk.find(d)) != -1:
                target_off = off - chunk_len + pos
                break
            if d_len <= chunk_len:
                buf = chunk[-(d_len - 1):]
            else:
                buf = chunk
        return target_off

    def bytes_to_u32array(self, byteorder: Literal["little", "big"]) -> None:
        self._prepare_write()

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
        self._prepare_write()

        for i in range(0, len(self.chunk), 4):
            self.chunk[i:i + 4] = self.chunk[i:i + 4][::-1]

    async def fraction_byte(self, byte: uint8 = uint8(0), div: int = 2) -> bool:
        assert div != 0
        if self.size is None:
            await self.get_size()

        await self.r_stream.seek(0)
        cnt = 0
        while True:
            chunk = await self.r_stream.read(self.CHUNKSIZE)
            if not chunk:
                break

            cnt += chunk.count(byte.value)
            if cnt * div >= self.size:
                return True
        return cnt * div >= self.size

    def encrypt(self, ctx: int) -> None:
        self._prepare_write()
        ctx = self._get_ctx(ctx)
        assert hasattr(ctx.obj, "encrypt")
        assert isinstance(ctx.attr, uint8)

        blocksize = ctx.attr.value
        assert blocksize != 0

        remainder = self.chunk[len(self.chunk) - (len(self.chunk) % blocksize):]
        if self.chunk == remainder:
            return
        del self.chunk[-len(remainder):]
        self.chunk_end -= len(remainder)

        ctx.obj.encrypt(self.chunk, self.chunk)

    def decrypt(self, ctx: int) -> None:
        self._prepare_write()
        ctx = self._get_ctx(ctx)
        assert hasattr(ctx.obj, "decrypt")
        assert isinstance(ctx.attr, uint8)

        blocksize = ctx.attr.value
        assert blocksize != 0

        remainder = self.chunk[len(self.chunk) - (len(self.chunk) % blocksize):]
        if self.chunk == remainder:
            return
        del self.chunk[-len(remainder):]
        self.chunk_end -= len(remainder)

        ctx.obj.decrypt(self.chunk, self.chunk)

    async def compress(self, ctx: int) -> None:
        self._prepare_write()
        self._prepare_compression()
        ctx = self._get_ctx(ctx)

        if isinstance(ctx.obj, zlib._Compress):
            await self._zlib_compress(ctx.obj)
        elif isinstance(ctx.obj, pyzstd.ZstdCompressor):
            assert type(ctx.attr) == bool
            await self._zstd_compress(ctx.obj, ctx.attr)
        else:
            assert 0

    async def decompress(self, ctx: int) -> None | int:
        self._prepare_write()
        self._prepare_compression()
        ctx = self._get_ctx(ctx)

        if isinstance(ctx.obj, zlib._Decompress):
            try:
                return await self._zlib_decompress(ctx.obj)
            except zlib.error as e:
                raise CryptoError("Invalid save!") from e
        elif isinstance(ctx.obj, (pyzstd.ZstdDecompressor, pyzstd.EndlessZstdDecompressor)):
            try:
                return await self._zstd_decompress(ctx.obj)
            except pyzstd.ZstdError as e:
                raise CryptoError("Invalid save!") from e
        else:
            assert 0

    async def checksum(self, ctx: int, start_off: int = -1, end_off: int = -1) -> None:
        self._prepare_write()
        ctx = self._get_ctx(ctx)

        if start_off < 0 or end_off < 0:
            if hasattr(ctx.obj, "update"):
                ctx.obj.update(self.chunk)
            elif isinstance(ctx.attr, Cint) and callable(ctx.obj):
                self.attr.value = ctx.obj(self.chunk)
            else:
                assert 0
            return

        assert start_off < end_off
        await self.r_stream.seek(start_off)

        for off in range(start_off, end_off, self.CHUNKSIZE):
            r_len = min(self.CHUNKSIZE, end_off - off)
            chunk = await self.r_stream.read(r_len)
            if not chunk:
                break

            if hasattr(ctx.obj, "update"):
                ctx.obj.update(chunk)
            elif isinstance(ctx.attr, Cint) and callable(ctx.obj):
                self.attr.value = ctx.obj(chunk)
            else:
                assert 0

    async def write_checksum(self, ctx: int, off: int) -> int:
        self._prepare_write()
        ctx = self._get_ctx(ctx)
        if hasattr(ctx.obj, "digest"):
            chks = ctx.obj.digest()
        elif isinstance(ctx.attr, Cint):
            chks = ctx.attr.as_bytes
        else:
            assert 0

        await self.w_stream.seek(off)
        return await self.w_stream.write(chks)

    def _create_ctx(self, obj: Any, attr: Any | None = None) -> int:
        x = CustomCryptoCtx(obj, attr)
        self.ctx_container[self.i] = x
        self.i += 1
        assert self.i <= 0xFF
        return self.i - 1

    def create_ctx_aes(self, key: bytes | bytearray, mode: int, **kwargs) -> int:
        cipher = AES.new(key, mode, **kwargs)
        blocksize = uint8(AES.block_size)
        return self._create_ctx(cipher, blocksize)

    def create_ctx_blowfish(self, key: bytes | bytearray, mode: int, **kwargs) -> int:
        cipher = Blowfish.new(key, mode, **kwargs)
        blocksize = uint8(Blowfish.block_size)
        return self._create_ctx(cipher, blocksize)

    def create_ctx_zlib_compress(self) -> int:
        self._prepare_compression()
        obj = zlib.decompressobj()
        return self._create_ctx(obj)

    def create_ctx_gzip_compress(self) -> int:
        self._prepare_compression()
        obj = zlib.compressobj(zlib.MAX_WBITS | 16)
        return self._create_ctx(obj)

    def create_ctx_zstd_compress(self, per_chunk_frame: bool = False) -> int:
        self._prepare_compression()
        obj = pyzstd.ZstdCompressor()
        attr = per_chunk_frame
        return self._create_ctx(obj, attr)

    def create_ctx_zlib_decompress(self) -> int:
        self._prepare_compression()
        obj = zlib.decompressobj()
        return self._create_ctx(obj)

    def create_ctx_gzip_decompress(self) -> int:
        self._prepare_compression()
        obj = zlib.decompressobj(zlib.MAX_WBITS | 16)
        return self._create_ctx(obj)

    def create_ctx_zstd_decompress(self, endless: bool = False) -> int:
        self._prepare_compression()
        if endless:
            obj = pyzstd.EndlessZstdDecompressor()
        else:
            obj = pyzstd.ZstdDecompressor()
        return self._create_ctx(obj)

    def create_ctx_crc32(self, seed: uint32 = uint32(0)) -> int:
        call = zlib.crc32
        return self._create_ctx(call, seed)

    def create_ctx_crc32c(self, seed: uint32 = uint32(0)) -> int:
        call = crc32c.crc32c
        return self._create_ctx(call, seed)

    def create_ctx_mmh3_u32(self, seed: uint32 = uint32(0)) -> int:
        call = partial(mmh3.hash, signed=False)
        return self._create_ctx(call, seed)

    def create_ctx_md5(self) -> int:
        update_obj = hashlib.md5()
        return self._create_ctx(update_obj)

    def create_ctx_sha1(self) -> int:
        update_obj = hashlib.sha1()
        return self._create_ctx(update_obj)

    @staticmethod
    def _decomp_max_size_calc(size: int, inc: int) -> None:
        if size + inc > SAVESIZE_MAX:
            raise CryptoError("Max size reached while decompressing!")

    async def _zlib_decompress(self, obj: zlib._Decompress) -> None | int:
        size = await self.w_stream.seek(0, 2)
        if obj.unconsumed_tail:
            while True:
                comp = obj.unconsumed_tail
                if not comp:
                    break
                decomp = obj.decompress(comp, self.CHUNKSIZE)
                self._decomp_max_size_calc(size, len(decomp))
                await self.w_stream.write(decomp)

        decomp = obj.decompress(self.chunk, self.CHUNKSIZE)
        self._decomp_max_size_calc(size, len(decomp))
        await self.w_stream.write(decomp)

        if obj.eof:
            eof_off = self.chunk_start + (len(self.chunk) - len(obj.unused_data)) 
            while True:
                decomp = obj.flush(self.CHUNKSIZE)
                if not decomp:
                    break
                self._decomp_max_size_calc(size, len(decomp))
                await self.w_stream.write(decomp)
            return eof_off # in r_stream

    async def _zstd_decompress(self, obj: pyzstd.ZstdDecompressor | pyzstd.EndlessZstdDecompressor) -> None | int:
        size = await self.w_stream.seek(0, 2)
        if obj.needs_input:
            while True:
                decomp = obj.decompress(bytes(), self.CHUNKSIZE)
                if not decomp:
                    break
                self._decomp_max_size_calc(size, len(decomp))
                await self.w_stream.write(decomp)

        decomp = obj.decompress(self.chunk, self.CHUNKSIZE)
        self._decomp_max_size_calc(size, len(decomp))
        await self.w_stream.write(decomp)

        if isinstance(obj, pyzstd.ZstdDecompressor) and obj.eof:
            eof_off = self.chunk_start + (len(self.chunk) - len(obj.unused_data))
            return eof_off # in r_stream

    async def _zlib_compress(self, obj: zlib._Compress) -> None:
        await self.w_stream.seek(0, 2)
        comp = obj.compress(self.chunk)
        await self.w_stream.write(comp)
        comp = obj.flush(zlib.Z_SYNC_FLUSH)
        await self.w_stream.write(comp)

    async def _zstd_compress(self, obj: pyzstd.ZstdCompressor, per_chunk_frame: bool) -> None:
        await self.w_stream.seek(0, 2)
        comp = obj.compress(self.chunk)
        await self.w_stream.write(comp)

        if per_chunk_frame:
            flush_mode = obj.FLUSH_FRAME
        else:
            flush_mode = obj.FLUSH_BLOCK
        comp = obj.flush(flush_mode)
        await self.w_stream.write(comp)

    @staticmethod
    async def obtain_files(path: str, exclude: list[str] | None = None, files: list[str] | None = None) -> list[str]:
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
                await CustomCrypto.obtain_files(entry_path, exclude, files)

        return files
