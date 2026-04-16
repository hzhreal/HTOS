from data.crypto.common import CustomCrypto as CC

class Crypt_Strider:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            crc = cc.create_ctx_crc32()
            await cc.checksum(crc, 4, 0x77FF + 1)
            await cc.write_checksum(crc, 0)
            cc.delete_ctx(crc)
            crc = cc.create_ctx_crc32()
            await cc.checksum(crc, 0x7804, cc.size)
            await cc.write_checksum(crc, 0x7800)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_Strider.encrypt_file(filepath)

