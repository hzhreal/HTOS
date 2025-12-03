from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_DSR:
    KEY = bytes([
        0x20, 0xEC, 0x4B, 0x75,
        0x19, 0xC2, 0xBD, 0x15,
        0xE7, 0x0C, 0x1E, 0xE4,
        0xB2, 0x04, 0xB8, 0xCB
    ])

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with CC(filepath) as cc:
                iv = await cc.r_stream.read(16)
                aes = cc.create_ctx_aes(Crypt_DSR.KEY, cc.AES.MODE_CBC, iv=iv)
                stop_off = cc.size - 32
                if stop_off < 0:
                    raise CryptoError("Invalid save!")
                while await cc.read(stop_off=stop_off):
                    await cc.decrypt(aes)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            iv = cc.gen_bytes(16)
            await cc.w_stream.write(iv)
            aes = cc.create_ctx_aes(Crypt_DSR.KEY, cc.AES.MODE_CBC, iv=iv)
            md5 = cc.create_ctx_md5()
            stop_off = cc.size - 32
            if stop_off < 0:
                raise CryptoError("Invalid save!")
            while await cc.read(stop_off=stop_off):
                await cc.encrypt(aes)
            await cc.checksum(md5, stop_off)
            await cc.write_checksum(md5, stop_off)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            decrypted = await cc.fraction_byte(data)
        if decrypted:
            await Crypt_DSR.encrypt_file(filepath)
