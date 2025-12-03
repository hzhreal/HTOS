from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_DI2:
    ZSTD_MAGIC = uint32(0xFD2FB528, "little")
    # this is a header from a save that will get applied when compressing
    # the header contains metadata such as game version
    # instead of figuring out how to generate one, here is a lazy approach
    # so here is one already from a save
    HEADER_FROM_SAVE = b"\xBF\xF5\x0F\x00\x0A\x00\x03\x00\x01\xD9\x0E\x51\x05\x00\x00\x00\x5A\x73\x74\x64\x00\x6E\x20\x00\x00\x00\x00\x01\x00"

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with CC(filepath, in_place=False) as cc:
                zstd = cc.create_ctx_zstd_decompress(endless=True)
                while await cc.read():
                    await cc.decompress(zstd)
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.w_stream.write(Crypt_DI2.HEADER_FROM_SAVE)
            zstd = cc.create_ctx_zstd_compress(per_chunk_frame=True)
            while await cc.read():
                await cc.compress(zstd)
    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            off = await cc.find(Crypt_DI2.ZSTD_MAGIC.as_bytes)
        if off == -1:
            await Crypt_DI2.encrypt_file(filepath)
