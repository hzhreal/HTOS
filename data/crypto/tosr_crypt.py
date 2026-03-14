from os.path import basename
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_ToSR:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            chks = uint32(0, "little")
            cc.set_ptr(4)
            while await cc.read(stop_off=0x25F8):
                cc.bytes_to_u32array("little")
                chks.value += sum(u32.value for u32 in cc.chunk)
            await cc.w_stream.seek(0)
            await cc.w_stream.write(chks.as_bytes)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if basename(filepath).startswith("TOSSaveData"):
            await Crypt_ToSR.encrypt_file(filepath)
