from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_MHR:
    SEED = uint32(0xFF_FF_FF_FF, "little", const=True)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            mmh3 = cc.create_ctx_mmh3_u32(Crypt_MHR.SEED)
            await cc.checksum(mmh3, 0, cc.size - 4)
            await cc.write_checksum(mmh3, cc.size - 4)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_MHR.encrypt_file(filepath)

