import aiofiles
import os

from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_Terraria:
    SECRET_KEY = "h3y_gUyZ".encode("utf-16-le")
    DEC_MAGIC = b"relogic"
    COMP_MAGIC = uint32(0x1AA2227E, "little").as_bytes

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_Terraria.file_check(filepath):
            return

        _, ext = os.path.splitext(filepath)

        async with CC(filepath, in_place=ext == ".plr") as cc:
            match ext:
                case ".plr":
                    aes = cc.create_ctx_aes(Crypt_Terraria.SECRET_KEY, cc.AES.MODE_CBC, iv=Crypt_Terraria.SECRET_KEY)
                    while await cc.read():
                        cc.decrypt(aes)
                        await cc.write()
                case ".wld":
                    zlib = cc.create_ctx_zlib_decompress()
                    cc.set_ptr(0x8)
                    while await cc.read():
                        await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_Terraria.file_check(filepath):
            return

        _, ext = os.path.splitext(filepath)

        async with CC(filepath, in_place=ext == ".plr") as cc:
            match ext:
                case ".plr":
                    aes = cc.create_ctx_aes(Crypt_Terraria.SECRET_KEY, cc.AES.MODE_CBC, iv=Crypt_Terraria.SECRET_KEY)
                    while await cc.read():
                        cc.encrypt(aes)
                        await cc.write()
                case ".wld":
                    zlib = cc.create_ctx_zlib_compress()
                    size = uint32(cc.size, "little").as_bytes
                    await cc.w_stream.write(Crypt_Terraria.COMP_MAGIC)
                    await cc.w_stream.write(size)
                    while await cc.read():
                        await cc.compress(zlib)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        unfiltered_files = await CC.obtain_files(folderpath)
        filtered_files = Crypt_Terraria.files_check(unfiltered_files)
        for filepath in filtered_files:
             async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(0x04)
                magic = await savegame.read(len(Crypt_Terraria.DEC_MAGIC))
             if magic != Crypt_Terraria.DEC_MAGIC:
                await Crypt_Terraria.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if not Crypt_Terraria.file_check(filepath):
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(0x04)
            magic = await savegame.read(len(Crypt_Terraria.DEC_MAGIC))
        if magic == Crypt_Terraria.DEC_MAGIC:
            await Crypt_Terraria.encrypt_file(filepath)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        filtered_paths = []
        for path in files:
            if path.endswith(".plr") or path.endswith(".wld"):
                filtered_paths.append(path)
        return filtered_paths

    @staticmethod
    def file_check(filepath: str) -> bool:
        return filepath.endswith(".plr") or filepath.endswith(".wld")

