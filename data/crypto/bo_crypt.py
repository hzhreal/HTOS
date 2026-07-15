from data.crypto.common import CustomCrypto as CC

class Crypt_BO:
    SECRET_KEY = b"Md8ea20lPcftYwsl496q63x9"
    IV         = b"0Peyx825"

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            des3 = cc.create_ctx_des3(Crypt_BO.SECRET_KEY, cc.DES3.MODE_CBC, iv=Crypt_BO.IV)
            while await cc.read():
                cc.decrypt(des3)
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            des3 = cc.create_ctx_des3(Crypt_BO.SECRET_KEY, cc.DES3.MODE_CBC, iv=Crypt_BO.IV)
            while await cc.read():
                cc.encrypt(des3)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_BO.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_BO.encrypt_file(filepath)

