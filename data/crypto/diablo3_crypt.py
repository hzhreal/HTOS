from os.path import basename
from data.crypto.common import CustomCrypto as CC

class Crypt_Diablo3:
    KEY1 = 0x305F92D8
    KEY2 = 0x2EC9A01B

    # Value found at the start of every encrypted file in the heroes folder
    # HEROES_ENC_MAGIC = b"\x13\x29\xCE\x3C"
    # The value above decrypted
    # HEROES_DEC_MAGIC = b"\xCB\xBB\x91\x0C"

    # prefs.dat seems to not be encrypted
    IGNORE = ("prefs.dat")

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if basename(filepath) in Crypt_Diablo3.IGNORE:
            return

        async with CC(filepath) as cc:
            xor_key1 = Crypt_Diablo3.KEY1
            xor_key2 = Crypt_Diablo3.KEY2
            while await cc.read():
                for i in range(len(cc.chunk)):
                    cc.chunk[i] ^= (xor_key1 & 0xFF)
                    tmp = cc.chunk[i] ^ xor_key1
                    xor_key1 = (xor_key1 >> 8) | (xor_key2 << 0x18)
                    xor_key2 = (xor_key2 >> 8) | (tmp      << 0x18)
                    xor_key1 &= 0xFF_FF_FF_FF
                    xor_key2 &= 0xFF_FF_FF_FF
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if basename(filepath) in Crypt_Diablo3.IGNORE:
            return

        async with CC(filepath) as cc:
            xor_key1 = Crypt_Diablo3.KEY1
            xor_key2 = Crypt_Diablo3.KEY2
            while await cc.read():
                for i in range(len(cc.chunk)):
                    tmp = cc.chunk[i] ^ xor_key1
                    cc.chunk[i] ^= (xor_key1 & 0xFF)
                    xor_key1 = (xor_key1 >> 8) | (xor_key2 << 0x18)
                    xor_key2 = (xor_key2 >> 8) | (tmp      << 0x18)
                    xor_key1 &= 0xFF_FF_FF_FF
                    xor_key2 &= 0xFF_FF_FF_FF
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath, exclude=list(Crypt_Diablo3.IGNORE))
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_non_printable_chars(3)
            if not is_dec:
                await Crypt_Diablo3.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath, exclude=list(Crypt_Diablo3.IGNORE))
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_non_printable_chars(3)
            if is_dec:
                await Crypt_Diablo3.encrypt_file(filepath)

