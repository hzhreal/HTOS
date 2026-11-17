import struct
from data.crypto.common import CustomCrypto as CC

class Crypt_LEGOMSH:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            b = await cc.ext_read(4, 4)
            h = 0xFF_FF_FF_FF
            h = ( (h * 0x01000193) & 0xFF_FF_FF_FF) ^ b[0]
            h = ( (h * 0x01000193) & 0xFF_FF_FF_FF) ^ b[1]
            h = ( (h * 0x01000193) & 0xFF_FF_FF_FF) ^ b[2]
            h = ( (h * 0x01000193) & 0xFF_FF_FF_FF) ^ b[3]
            h ^= 0xFF_FF_FF_FF
            h = struct.pack("<I", h)
            await cc.ext_write(8, h)

            cc.set_ptr(16)
            h = 0xFF_FF_FF_FF
            while await cc.read():
                for b in cc.chunk:
                    h = ( (h * 0x01000193) & 0xFF_FF_FF_FF) ^ b
            h ^= 0xFF_FF_FF_FF
            h = struct.pack("<I", h)
            await cc.ext_write(12, h)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_LEGOMSH.encrypt_file(filepath)

