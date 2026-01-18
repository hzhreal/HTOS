import aiofiles
from data.crypto.common import CustomCrypto as CC

class Crypt_RCube:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_RCube.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress()
            header = await cc.r_stream.read(0xC)
            await cc.w_stream.write(header)
            cc.set_ptr(0xC)
            while await cc.read():
                await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_RCube.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress()
            header = await cc.r_stream.read(0xC)
            await cc.w_stream.write(header)
            cc.set_ptr(0xC)
            while await cc.read():
                await cc.compress(zlib)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_RCube.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(0xC)
                header = await savegame.read(2)
            if CC.is_valid_zlib_header(header):
                await Crypt_RCube.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if not Crypt_RCube.file_check(filepath):
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(0xC)
            header = await savegame.read(2)
        if not CC.is_valid_zlib_header(header):
            await Crypt_RCube.encrypt_file(filepath)

    @staticmethod
    def file_check(filepath: str) -> bool:
        return filepath.endswith(".dat")

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        valid = []
        for path in files:
            if path.endswith(".dat"):
                valid.append(path)
        return valid

