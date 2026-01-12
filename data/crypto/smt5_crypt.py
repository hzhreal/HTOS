import aiofiles
from data.crypto.common import CustomCrypto as CC

class Crypt_SMT5:
    SECRET_KEY = bytes([
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66
    ])

    MAGIC = b"GVAS"

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with CC(filepath) as cc:
                aes = cc.create_ctx_aes(Crypt_SMT5.SECRET_KEY, cc.AES.MODE_ECB)
                while await cc.read():
                    cc.decrypt(aes)
                    await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            aes = cc.create_ctx_aes(Crypt_SMT5.SECRET_KEY, cc.AES.MODE_ECB)
            sha1 = cc.create_ctx_sha1()

            await cc.checksum(sha1, 0x40, cc.size)
            await cc.write_checksum(sha1, 0)

            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(0x40)
            magic = await savegame.read(len(Crypt_SMT5.MAGIC))

        if magic == Crypt_SMT5.MAGIC:
            await Crypt_SMT5.encrypt_file(filepath)
