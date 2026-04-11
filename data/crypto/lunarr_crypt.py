from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_LunarR:
    @staticmethod
    async def encrypt_file(filepath: str, savepairname: str) -> None:
        if not Crypt_LunarR.savepairname_check(savepairname):
            return

        async with CC(filepath) as cc:
            if "LUNAR" in savepairname:
                # lunar 1
                checksum = uint32(0, "little")
                while await cc.read(stop_off=cc.size - 4):
                    cc.bytes_to_u32array("little")
                    checksum.value += sum(u32.value for u32 in cc.chunk)
                await cc.ext_write(cc.size - 4, checksum.as_bytes)
            else:
                # lunar 2
                checksum = uint32(0, "little")
                cc.set_ptr(0x300)
                while await cc.read():
                    checksum.value += sum(cc.chunk)
                await cc.w_stream.seek(0x204)
                await cc.w_stream.write(checksum.as_bytes)

    @staticmethod
    async def check_enc_ps(filepath: str, savepairname: str) -> None:
        if not Crypt_LunarR.savepairname_check(savepairname):
            return

        await Crypt_LunarR.encrypt_file(filepath, savepairname)

    @staticmethod
    def savepairname_check(savepairname: str) -> bool:
        return "LUNAR" in savepairname or "SAVEDATA" in savepairname

