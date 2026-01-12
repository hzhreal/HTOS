from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_Digimon:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            await cc.w_stream.seek(8)
            await cc.w_stream.write(bytes([0] * 4))
            chks = uint32(0, "little")
            while await cc.read():
                chks.value += sum(cc.chunk)
            await cc.w_stream.seek(8)
            await cc.w_stream.write(chks.as_bytes)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        await Crypt_Digimon.check_enc_ps(filepath)
