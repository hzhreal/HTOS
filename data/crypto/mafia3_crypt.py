from data.crypto.common import CustomCrypto as CC

class Crypt_Mafia3:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            crc = cc.create_ctx_crc32()
            await cc.checksum(crc, 0, cc.size - 4)
            await cc.write_checksum(crc, cc.size - 4)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_Mafia3.encrypt_file(filepath)

