import struct
from os.path import basename
from data.crypto.common import CustomCrypto as CC

class Crypt_DeadRising:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if basename(filepath) != "deadrising":
            return

        async with CC(filepath) as cc:
            while await cc.read():
                if not cc._trim_chunk(20):
                    break
                for i in range(0, len(cc.chunk), 20):
                    l = 0
                    r = 0
                    for j in range(16):
                        l += cc.chunk[i + j]
                        l &= 0xFF_FF
                        if j & 1 == 0:
                            r += cc.chunk[i + j]
                        else:
                            r -= cc.chunk[i + j]
                        r &= 0xFF_FF
                    cc.chunk[i + 16:(i + 16) + 2] = struct.pack("<H", l)
                    cc.chunk[i + 18:(i + 18) + 2] = struct.pack("<H", r)
                await cc.write()

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            if basename(filepath) != "deadrising":
                continue

            await Crypt_DeadRising.encrypt_file(filepath)

