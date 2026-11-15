import struct
from data.crypto.common import CustomCrypto as CC

class Crypt_Tsushima:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            buf = await cc.ext_read(0, 8)
            version, size = struct.unpack("<II", buf)
            csum = (version + size) & 0xFF_FF_FF_FF
            cc.set_ptr(0xC)
            while await cc.read():
                csum += sum(cc.chunk) & 0xFF_FF_FF_FF
            csum = struct.pack("<I", csum)
            await cc.ext_write(8, csum)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_Tsushima.encrypt_file(filepath)

