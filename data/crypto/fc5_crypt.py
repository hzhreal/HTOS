from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_FC5:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            crc = cc.create_ctx_crc32()
            await cc.r_stream.seek(0x8)
            msg_len = uint32(await cc.r_stream.read(4), "little").value
            await cc.checksum(crc, 0x10, 0x10 + msg_len)
            await cc.write_checksum(crc, 0xC)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        await Crypt_FC5.encrypt_file(filepath)

