import aiofiles
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32

class Crypt_GS3:
    SECRET_KEY = bytes([
        0x4C, 0x08, 0x54, 0x71, 0x3A, 0x51, 0xA1, 0x04,
        0xFE, 0x9B, 0x1F, 0x75, 0x22, 0x75, 0xD2, 0x36,
        0x4F, 0x60, 0x06, 0x44, 0xB6, 0xDE, 0x4F, 0x54,
        0x73, 0xDB, 0x5B, 0x92, 0x27, 0x3E, 0xC0, 0xAF,
    ])
    MAGIC = bytes([
        0x1A, 0x47, 0x77, 0x92, 0x4F, 0x98, 0xF2, 0x82
    ])
    DEC_MAGIC = b"GVAS"
    HEADER_SIZE = 16

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            buf = await cc.ext_read(Crypt_GS3.HEADER_SIZE - 8, 8)
            decomp_size = uint32(buf[:4], "little").value
            if decomp_size > cc.SAVESIZE_MAX:
                raise CryptoError("Unsupported save!")
            cipher_size = uint32(buf[4:], "little").value
            if cipher_size % cc.AES.block_size != 0:
                raise CryptoError("Invalid save!")

            aes = cc.create_ctx_aes(Crypt_GS3.SECRET_KEY, cc.AES.MODE_ECB)
            cc.set_ptr(Crypt_GS3.HEADER_SIZE)
            while await cc.read():
                cc.decrypt(aes)
                await cc.write()
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, Crypt_GS3.HEADER_SIZE + cipher_size)
            await cc.pkcs7_pad_post(cc.AES.block_size)
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress()
            l = 0
            await cc.copy(0, Crypt_GS3.HEADER_SIZE)
            cc.set_ptr(Crypt_GS3.HEADER_SIZE)
            while await cc.read():
                l += await cc.decompress(zlib)
                if l > decomp_size:
                    raise CryptoError("Invalid save!")
            if l != decomp_size:
                raise CryptoError("Invalid save!")

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, Crypt_GS3.HEADER_SIZE)
            decomp_size = uint32(cc.size - Crypt_GS3.HEADER_SIZE, "little").as_bytes
            await cc.w_stream.seek(Crypt_GS3.HEADER_SIZE - 8)
            await cc.w_stream.write(decomp_size)
            zlib = cc.create_ctx_zlib_compress()
            l = 0
            cc.set_ptr(Crypt_GS3.HEADER_SIZE)
            while await cc.read():
                l += await cc.compress(zlib)
            l += await cc.compress_post(zlib)
            l = l + (cc.AES.block_size - (l % cc.AES.block_size))
            l_ = uint32(l, "little")
            if l != l_.value:
                raise CryptoError("Invalid save!")
            await cc.w_stream.seek(Crypt_GS3.HEADER_SIZE - 4)
            await cc.w_stream.write(l_.as_bytes)
            await cc.pkcs7_pad_pre(cc.AES.block_size)
        async with CC(filepath) as cc:
            aes = cc.create_ctx_aes(Crypt_GS3.SECRET_KEY, cc.AES.MODE_ECB)
            cc.set_ptr(Crypt_GS3.HEADER_SIZE)
            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                m1 = await savegame.read(len(Crypt_GS3.MAGIC))
                await savegame.seek(Crypt_GS3.HEADER_SIZE)
                m2 = await savegame.read(len(Crypt_GS3.DEC_MAGIC))
            if m1 == Crypt_GS3.MAGIC and m2 != Crypt_GS3.DEC_MAGIC:
                await Crypt_GS3.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                m1 = await savegame.read(len(Crypt_GS3.MAGIC))
                await savegame.seek(Crypt_GS3.HEADER_SIZE)
                m2 = await savegame.read(len(Crypt_GS3.DEC_MAGIC))
            if m1 == Crypt_GS3.MAGIC and m2 == Crypt_GS3.DEC_MAGIC:
                await Crypt_GS3.encrypt_file(filepath)

