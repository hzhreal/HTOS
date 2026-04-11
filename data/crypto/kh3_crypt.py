from data.crypto.common import CustomCrypto as CC

class Crypt_KH3:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            crc = cc.create_ctx_crc32()
            await cc.checksum(crc, 0x10, cc.size)
            await cc.write_checksum(crc, 0xC)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        await Crypt_KH3.encrypt_file(filepath)

