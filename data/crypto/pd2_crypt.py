from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32

class Crypt_PD2:
    SAVE_VERSION = 10
    BLOCK_VERSION = 10
    BLOCKS = 3 # header, gamedata, footer

    HASH_KEY = bytes([
        0x1A, 0x1F, 0x32, 0x2C
    ])
    MD5_MASK = 0xFF_FF_FF_FF_FF_FF_FF_FF

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            save_version = uint32(await cc.ext_read(0, 4), "little").value
            if save_version != Crypt_PD2.SAVE_VERSION:
                return
            i = 4

            for _ in range(Crypt_PD2.BLOCKS):
                # block is
                # u32 size (not counting itself)
                # u32 version
                # payload
                # md5 digest

                buf = await cc.ext_read(i, 8)
                block_size = uint32(buf[:4], "little").value
                block_version = uint32(buf[4:], "little").value
                if block_version != Crypt_PD2.BLOCK_VERSION:
                    i += block_size + 4
                    continue
                i += 8

                payload_size = block_size - 20
                if payload_size < 0:
                    raise CryptoError("Invalid save!")
                md5 = cc.create_ctx_md5_any(MASK=Crypt_PD2.MD5_MASK)
                await cc.checksum(md5, i, i + payload_size)
                i += payload_size
                await cc.write_checksum(md5, i)
                i += 16

            k = Crypt_PD2.HASH_KEY
            md5 = cc.create_ctx_md5_any(MASK=Crypt_PD2.MD5_MASK)
            i = 0
            while await cc.read(stop_off=cc.size - 16):
                c = cc.chunk
                for j in range(len(c)):
                    # if (c[j] + k[i % 4]) is odd
                    if (c[j] + k[i & 3]) & 1:
                        c[j] = i % 7
                    i += 1
                await cc.checksum(md5)
            await cc.write_checksum(md5, cc.size - 16)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_PD2.encrypt_file(filepath)

