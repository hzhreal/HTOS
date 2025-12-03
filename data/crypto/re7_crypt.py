from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_RE7:
    SEED = uint32(0xFF_FF_FF_FF, "little")

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            mmh3 = cc.create_ctx_mmh3_u32(Crypt_RE7.SEED)
            await cc.checksum(mmh3, end_off=cc.size - 4)
            await cc.write_checksum(mmh3, cc.size - 4)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        await Crypt_RE7.encrypt_file(filepath)
