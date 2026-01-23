import aiofiles
from data.crypto.common import CustomCrypto as CC

class Crypt_LaNoire:
    SAVE_KEY = b"Wr9uFi4yi*?OESwiavv$ayIAp+u23PIe"
    PROFILE_KEY = b"_!pH4ThU-7N?u&eph4$eaC!aTHaQ5U7u"
    DEC_MAGIC = b"\x5A\x3F\x28\x8B"

    @staticmethod
    async def decrypt_file(filepath: str, savepairname: str) -> None:
        if not Crypt_LaNoire.savepairname_check(savepairname):
            return

        if "SAVEGAME" in savepairname:
            key = Crypt_LaNoire.SAVE_KEY
        else:
            key = Crypt_LaNoire.PROFILE_KEY

        async with CC(filepath) as cc:
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CBC, iv=bytes([0] * cc.AES.block_size))

            while await cc.read():
                cc.decrypt(aes)
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str, savepairname: str) -> None:
        if not Crypt_LaNoire.savepairname_check(savepairname):
            return

        if "SAVEGAME" in savepairname:
            key = Crypt_LaNoire.SAVE_KEY
        else:
            key = Crypt_LaNoire.PROFILE_KEY

        async with CC(filepath) as cc:
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CBC, iv=bytes([0] * cc.AES.block_size))

            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str, savepairname: str) -> None:
        if not Crypt_LaNoire.savepairname_check(savepairname):
            return

        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                magic = await savegame.read(len(Crypt_LaNoire.DEC_MAGIC))
            if magic != Crypt_LaNoire.DEC_MAGIC:
                await Crypt_LaNoire.decrypt_file(filepath, savepairname)

    @staticmethod
    async def check_enc_ps(filepath: str, savepairname: str) -> None:
        if not Crypt_LaNoire.savepairname_check(savepairname):
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            magic = await savegame.read(len(Crypt_LaNoire.DEC_MAGIC))
        if magic == Crypt_LaNoire.DEC_MAGIC:
            await Crypt_LaNoire.encrypt_file(filepath, savepairname)

    @staticmethod
    def savepairname_check(savepairname: str) -> bool:
        return "SAVEGAME" in savepairname or "USERPREFERENCES" in savepairname
