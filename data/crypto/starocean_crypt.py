from data.crypto.common import CustomCrypto as CC

class Crypt_StarOcean:
    SECRET_KEY = bytes([
        0xE0, 0xBA, 0x27, 0x54, 0x6C, 0x83, 0xAD, 0x14
    ])

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        k = Crypt_StarOcean.SECRET_KEY
        async with CC(filepath) as cc:
            while await cc.read():
                c = cc.chunk
                for i in range(len(cc.chunk)):
                    k_fwd = k[i % 8]
                    k_rev = k[7 - (i % 8)]
                    c[i] = ( (c[i] ^ k_fwd) - k_rev ) & 0xFF
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        k = Crypt_StarOcean.SECRET_KEY
        async with CC(filepath) as cc:
            while await cc.read():
                c = cc.chunk
                for i in range(len(cc.chunk)):
                    k_fwd = k[i % 8]
                    k_rev = k[7 - (i % 8)]
                    c[i] = ( (c[i] + k_rev) & 0xFF ) ^ k_fwd
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_StarOcean.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_StarOcean.encrypt_file(filepath)

