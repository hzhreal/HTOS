import aiofiles
from typing import Literal

from data.crypto.common import CustomCrypto as CC

# both dying light 1 & 2 uses gzip, also dead island 1

class Crypt_DL:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            gzip = cc.create_ctx_gzip_decompress()
            while await cc.read():
                await cc.decompress(gzip)

    @staticmethod
    async def encrypt_file(filepath: str, _version: Literal["DL1", "DL2", "DI1"]) -> None:
        async with CC(filepath, in_place=False) as cc:
            gzip = cc.create_ctx_gzip_compress()
            while await cc.read():
                await cc.compress(gzip)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                magic = await savegame.read(3)
            if magic == b"\x1F\x8B\x08":
                await Crypt_DL.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str, _version: Literal["DL1", "DL2", "DI1"]) -> None:
        async with aiofiles.open(filepath, "rb") as savegame:
            magic = await savegame.read(3)
        if magic != b"\x1F\x8B\x08":
            await Crypt_DL.encrypt_file(filepath, _version)

