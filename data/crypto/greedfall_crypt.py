import aiofiles
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_GreedFall:
    MAX_BLOCKS = 10
    GZIP_MAGIC = b"\x1F\x8B\x08"

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_GreedFall.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            i = 168
            await cc.copy(0, i)
            cc.set_ptr(i)
            blocks = 0
            # game seems to have concatenated gzip streams which is not supported by our api
            # they seem to use the same 10 byte gzip header on the streams
            header = await cc.ext_read(i, 10)
            while i < cc.size:
                if blocks >= Crypt_GreedFall.MAX_BLOCKS:
                    raise CryptoError("Invalid save!")

                end = await cc.find(header, i + len(header))
                if end == -1:
                    end = cc.size

                gzip = cc.create_ctx_gzip_decompress()
                cc.set_ptr(i)
                while await cc.read(stop_off=end):
                    await cc.decompress(gzip)
                i = end
                blocks += 1
                cc.delete_ctx(gzip)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_GreedFall.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, 168)
            cc.set_ptr(168)
            gzip = cc.create_ctx_gzip_compress()
            while await cc.read():
                await cc.compress(gzip)
            await cc.compress_post(gzip)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_GreedFall.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(168)
                header = await savegame.read(len(Crypt_GreedFall.GZIP_MAGIC))
            if header == Crypt_GreedFall.GZIP_MAGIC:
                await Crypt_GreedFall.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_GreedFall.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(168)
                header = await savegame.read(len(Crypt_GreedFall.GZIP_MAGIC))
            if header != Crypt_GreedFall.GZIP_MAGIC:
                await Crypt_GreedFall.encrypt_file(filepath)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        filtered_files = []
        for path in files:
            if path.lower().endswith(".fs"):
                filtered_files.append(path)
        return filtered_files

    @staticmethod
    def file_check(path: str) -> bool:
        return path.lower().endswith(".fs")

