import zstandard as zstd

from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32

class Crypt_DI2:
    class DI2(CC):
        ZSTD_MAGIC = uint32(0xFD2FB528, "little").as_bytes
        def __init__(self, filepath: str) -> None:
            super().__init__(filepath, in_place=False)

        async def compress(self) -> None:
            assert not self.in_place
            await self.w_stream.seek(0, 2)
            while await self.read():
                comp = zstd.compress(self.chunk)
                await self.w_stream.write(comp)

        async def decompress(self) -> None:
            assert not self.in_place
            ctx = zstd.ZstdDecompressor()
            ptr = 0
            while True:
                off = await self.find(self.ZSTD_MAGIC, ptr)
                if off == -1:
                    break
                next_off = await self.find(self.ZSTD_MAGIC, off + len(self.ZSTD_MAGIC))
                if next_off != -1:
                    r_size = next_off - off
                else:
                    r_size = self.size - off

                if r_size > self.CHUNKSIZE:
                    raise CryptoError("Unsupported save!")
                await self.r_stream.seek(off)
                comp = await self.r_stream.read(r_size)
                if not comp:
                    break
                try:
                    fheader = zstd.get_frame_parameters(comp[:18])
                    if fheader.content_size > self.CHUNKSIZE:
                        raise CryptoError("Unsupported save!")
                    decomp = ctx.decompress(comp, self.CHUNKSIZE, allow_extra_data=True)
                except zstd.ZstdError:
                    raise CryptoError("Invalid save!")
                size = await self.w_stream.seek(0, 2)
                if size + len(decomp) > self.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")
                await self.w_stream.write(decomp)
                ptr = off + r_size

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with Crypt_DI2.DI2(filepath) as cc:
                header = await cc.r_stream.read(0x1D)
                await cc.w_stream.write(header)
                cc.set_ptr(0x1D)
                await cc.decompress()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with Crypt_DI2.DI2(filepath) as cc:
            header = await cc.r_stream.read(0x1D)
            await cc.w_stream.write(header)
            cc.set_ptr(0x1D)
            await cc.compress()

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            off = await cc.find(Crypt_DI2.DI2.ZSTD_MAGIC)
        if off == -1:
            await Crypt_DI2.encrypt_file(filepath)
