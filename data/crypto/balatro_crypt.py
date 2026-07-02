from data.crypto.common import CustomCrypto as CC

class Crypt_Balatro:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress(wbits=-15)
            while await cc.read():
                await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress(wbits=-15)
            while await cc.read():
                await cc.compress(zlib)
            await cc.compress_post(zlib)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if not is_dec:
                await Crypt_Balatro.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if is_dec:
                await Crypt_Balatro.encrypt_file(filepath)

