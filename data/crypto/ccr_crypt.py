from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_CCR:
    SECRET_KEY = bytes([
        0x12, 0xB9, 0x36, 0xAC, 0x7A, 0x12, 0x53, 0x01,
        0x7E, 0x43, 0x09, 0x66, 0x63, 0x83, 0xD4, 0x9F,
        0x67, 0x61, 0x3E, 0x56, 0x39, 0x38, 0x72, 0x72
    ])
    SIZE = 0x1050
    ROLLING_INIT = 0xD971

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            blowfish = cc.create_ctx_blowfish(Crypt_CCR.SECRET_KEY, cc.Blowfish.MODE_ECB)
            while await cc.read(stop_off=Crypt_CCR.SIZE):
                cc.ES32()
                cc.decrypt(blowfish)
                cc.ES32()
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            blowfish = cc.create_ctx_blowfish(Crypt_CCR.SECRET_KEY, cc.Blowfish.MODE_ECB)
            chks = uint32(0, "little")
            state = Crypt_CCR.ROLLING_INIT
            while await cc.read(stop_off=Crypt_CCR.SIZE):
                if cc.chunk_end != Crypt_CCR.SIZE:
                    n = 0
                else:
                    n = 4
                for i in range(len(cc.chunk) - n):
                    b = cc.chunk[i]
                    xor_byte = ((state >> 8) ^ b) & 0xFF
                    chks.value += xor_byte
                    state = ((state & 0xFFFF) + xor_byte) * 0xCE6D + 0x58BF
                    state &= 0xFFFF
                if n != 0:
                    cc.chunk[-n:] = chks.as_bytes
                cc.ES32()
                cc.encrypt(blowfish)
                cc.ES32()
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                dec = await cc.fraction_byte()
            if not dec:
                await Crypt_CCR.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            dec = await cc.fraction_byte()
        if dec:
            await Crypt_CCR.encrypt_file(filepath)

