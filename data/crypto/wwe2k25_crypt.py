import aiofiles
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32

class Crypt_WWE2K25:
    MAGIC = b"ZLIB"

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, 16)

            buf = await cc.ext_read(8, 8)
            comp_size = uint32(buf[:4], "little").value
            decomp_size = uint32(buf[4:], "little").value

            zlib = cc.create_ctx_zlib_decompress()
            s = 0
            cc.set_ptr(16)
            while await cc.read(stop_off=16 + comp_size):
                s += await cc.decompress(zlib)
                if s > decomp_size:
                    raise CryptoError("Invalid save!")
            if s != decomp_size:
                raise CryptoError("Invalid save!")

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, 16)

            decomp_size = cc.size - 16
            s = uint32(decomp_size, "little")
            if decomp_size != s.value:
                raise CryptoError("Invalid save!")
            decomp_size = s.as_bytes
            comp_size = 0

            zlib = cc.create_ctx_zlib_compress()
            cc.set_ptr(16)
            while await cc.read():
                comp_size += await cc.compress(zlib)
            comp_size += await cc.compress_post(zlib)
            s = uint32(comp_size, "little")
            if comp_size != s.value:
                raise CryptoError("Invalid save!")
            comp_size = s.as_bytes

            await cc.w_stream.seek(8)
            await cc.w_stream.write(comp_size + decomp_size)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                h1 = await savegame.read(4)
                await savegame.seek(16)
                h2 = await savegame.read(2)
            if h1 == Crypt_WWE2K25.MAGIC and CC.is_valid_zlib_header(h2):
                await Crypt_WWE2K25.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                h1 = await savegame.read(4)
                await savegame.seek(16)
                h2 = await savegame.read(2)
            if h1 == Crypt_WWE2K25.MAGIC and not CC.is_valid_zlib_header(h2):
                await Crypt_WWE2K25.encrypt_file(filepath)

