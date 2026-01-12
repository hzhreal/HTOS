import aiofiles
from os.path import basename
from data.crypto.common import CustomCrypto as CC

class Crypt_Sdew:
    EXCLUDE = ["startup_preferences", "SaveGameInfo"]
    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath, Crypt_Sdew.EXCLUDE)
        for filepath in files:
            async with CC(filepath, in_place=False) as cc:
                zlib = cc.create_ctx_zlib_decompress()
                while await cc.read():
                    await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if basename(filepath) in Crypt_Sdew.EXCLUDE:
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress()
            while await cc.read():
                await cc.compress(zlib)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if basename(filepath) in Crypt_Sdew.EXCLUDE:
            return
        async with aiofiles.open(filepath, "rb") as savegame:
            header = await savegame.read(2)
        if not await CC.is_valid_zlib_header(header):
            await Crypt_Sdew.encrypt_file(filepath)
