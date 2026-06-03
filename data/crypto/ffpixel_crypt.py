from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_FFPixel:
    # pbkdf-sha1:
    # password "TKX73OHHK1qMonoICbpVT0hIDGe7SkW0"
    # salt "71Ba2p0ULBGaE6oJ7TjCqwsls1jBKmRL"
    # key 0...31, iv 32...63
    SECRET_KEY = bytes([
        0x61, 0x09, 0x07, 0x00, 0xB9, 0xC3, 0xB8, 0xB9,
        0x42, 0x15, 0x99, 0xE7, 0x9C, 0xA5, 0x7B, 0x87,
        0xBE, 0xA9, 0x32, 0xD3, 0x79, 0x7B, 0xAD, 0x76,
        0x63, 0xED, 0x4D, 0xDE, 0x0A, 0x94, 0x3C, 0xC5
    ])
    IV = bytes([
        0x02, 0x24, 0xF9, 0x77, 0x1F, 0xDB, 0x6E, 0x0E,
        0x3B, 0xD5, 0x08, 0xD7, 0xB7, 0x95, 0xBF, 0x2E,
        0x0C, 0xBD, 0x17, 0x69, 0x42, 0x68, 0x0A, 0x63,
        0x7B, 0x12, 0xBC, 0x62, 0x73, 0xDB, 0x2E, 0xBB
    ])

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            rijndael = cc.create_ctx_rijndael(
                Crypt_FFPixel.SECRET_KEY, CC.Rijndael.MODE_CBC, 32, iv=Crypt_FFPixel.IV
            )
            while await cc.read():
                cc.decrypt(rijndael)
                await cc.write()
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
            size = await cc.w_stream.seek(0, 2)
            # round up to nearest multiple of the blocksize
            size_rounded = (size + 31) & ~31
            if size_rounded > cc.SAVESIZE_MAX:
                raise CryptoError("Savegame is too large to process!")
            p = size_rounded - size
            if p != 0:
                await cc.w_stream.write(bytes(size_rounded - size))

        async with CC(filepath) as cc:
            rijndael = cc.create_ctx_rijndael(
                Crypt_FFPixel.SECRET_KEY, CC.Rijndael.MODE_CBC, 32, iv=Crypt_FFPixel.IV
            )
            while await cc.read():
                cc.encrypt(rijndael)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if not is_dec:
                await Crypt_FFPixel.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if is_dec:
                await Crypt_FFPixel.encrypt_file(filepath)

