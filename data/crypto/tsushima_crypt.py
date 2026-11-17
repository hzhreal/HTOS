from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_Tsushima:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            buf = await cc.ext_read(0, 8)
            version = uint32(buf[:4], "little").value
            size = uint32(buf[4:], "little").value
            csum = uint32(version + size, "little")
            cc.set_ptr(0xC)
            while await cc.read():
                csum.value += sum(cc.chunk)
            await cc.ext_write(8, csum.as_bytes)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_Tsushima.encrypt_file(filepath)

