from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_RE5:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            cc.set_ptr(0x38)
            chks = uint32(0, "little")
            while await cc.read(stop_off=0x52D8):
                cc.bytes_to_u32array("little")
                chks.value += sum(u32.value for u32 in cc.chunk)
            await cc.ext_write(0x30, chks.as_bytes)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_RE5.encrypt_file(filepath)

