import zstandard as zstd
import cityhash

from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32, uint64

class Crypt_DI2:
    # CityHash cannot be streamed, whole message has to be in memory
    ENABLE_CITYHASH = True
    class DI2(CC):
        ZSTD_MAGIC   = uint32(0xFD2FB528, "little").as_bytes
        START_MARKER = uint32(0x510ED901, "little").as_bytes
        END_MARKER   = uint32(0x5A13FC42, "little").as_bytes

        def __init__(self, filepath: str) -> None:
            super().__init__(filepath, in_place=False)
            self.start = -1
            self.end   = -1
            self.csum  = bytes()

        def prepared(self) -> bool:
            return self.start != -1 and self.end != -1

        async def prepare(self) -> None:
            start_marker = await self.ext_read(8, 4)
            if start_marker != self.START_MARKER:
                raise CryptoError("Invalid save!")
            length = uint32(await self.ext_read(12, 4), "little")
            start = 12 + len(length.as_bytes) + length.value
            end = await self.rfind(self.END_MARKER, self.size - 8, start)
            if end == -1:
                raise CryptoError("Invalid save!")
            if end + 12 > self.size:
                raise CryptoError("Invalid save!")
            self.start = start
            self.end = end

        async def checksum(self) -> None:
            if not Crypt_DI2.ENABLE_CITYHASH:
                return

            assert self.prepared()
            start = self.start
            end = self.end

            await self.r_stream.seek(start)
            msg = await self.r_stream.read(end - start) # whole message in memory
            self.csum = uint64(cityhash.CityHash64(msg), "little").as_bytes

        async def checksum_write(self) -> None:
            if not Crypt_DI2.ENABLE_CITYHASH:
                return

            assert self.prepared()
            assert self.csum

            await self.w_stream.seek(-8, 1)
            await self.w_stream.write(self.csum)

        async def compress(self) -> None:
            assert not self.in_place
            assert self.prepared()

            start = self.start
            end = self.end

            await self.copy(0, start)
            size = start

            cctx = zstd.ZstdCompressor()
            self.set_ptr(start)
            while await self.read(stop_off=end):
                comp = cctx.compress(self.chunk)

                cs = uint32(len(comp), "little").as_bytes
                ds = uint32(len(self.chunk), "little").as_bytes

                l = len(cs) + len(ds) + len(comp)
                if size + l > self.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")
                await self.w_stream.write(cs)
                await self.w_stream.write(ds)
                await self.w_stream.write(comp)
                size += l
            await self.copy(end, end + 12)

        async def decompress(self) -> None:
            assert not self.in_place
            assert self.prepared()

            start = self.start
            end = self.end

            await self.copy(0, start)
            i = start
            size = start

            dctx = zstd.ZstdDecompressor()
            while i < end:
                buf = await self.ext_read(i, 8)
                cs = uint32(buf[:4], "little").value
                ds = uint32(buf[4:], "little").value
                if i + 8 + cs > end:
                    raise CryptoError("Invalid save!")
                if cs > self.CHUNKSIZE:
                    raise CryptoError("Unsupported save!")
                if ds > self.CHUNKSIZE:
                    raise CryptoError("Unsupported save!")
                if size + ds > self.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")

                try:
                    buf = await self.ext_read(i + 8, 18)
                    fheader = zstd.get_frame_parameters(buf)
                    if fheader.content_size > self.CHUNKSIZE:
                        raise CryptoError("Unsupported save!")
                    c = await self.ext_read(i + 8, cs)
                    d = dctx.decompress(c, max_output_size=ds, read_across_frames=False, allow_extra_data=False)
                except zstd.ZstdError:
                    raise CryptoError("Invalid save!")
                assert len(d) == ds
                await self.w_stream.write(d)
                size += ds
                i += 8 + cs
            await self.copy(end, end + 12)

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with Crypt_DI2.DI2(filepath) as cc:
            await cc.prepare()
            await cc.decompress()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with Crypt_DI2.DI2(filepath) as cc:
            await cc.prepare()
            await cc.checksum()
            await cc.compress()
            await cc.checksum_write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                off = await cc.find(Crypt_DI2.DI2.ZSTD_MAGIC)
            if off != -1:
                await Crypt_DI2.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                off = await cc.find(Crypt_DI2.DI2.ZSTD_MAGIC)
            if off == -1:
                await Crypt_DI2.encrypt_file(filepath)

