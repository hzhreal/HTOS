from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_Rev2:
    SECRET_KEY = b"zW$2eWaHNdT~6j86T_&j"

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            blowfish_ecb = cc.create_ctx_blowfish(Crypt_Rev2.SECRET_KEY, cc.Blowfish.MODE_ECB)
            cc.set_ptr(0x20)
            while await cc.read():
                cc.ES32()
                cc.decrypt(blowfish_ecb)
                cc.ES32()
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            blowfish_ecb = cc.create_ctx_blowfish(Crypt_Rev2.SECRET_KEY, cc.Blowfish.MODE_ECB)
            sha1 = cc.create_ctx_sha1()

            dwadd = uint32(0, "little")
            cc.set_ptr(0x20)
            while await cc.read(stop_off=0x19490):
                cc.bytes_to_u32array("little")
                dwadd.value += sum(u32.value for u32 in cc.chunk)
            cc.set_ptr(0x194A0)
            while await cc.read(stop_off=0x1284C0):
                cc.bytes_to_u32array("little")
                dwadd.value += sum(u32.value for u32 in cc.chunk)
            await cc.w_stream.seek(0x18)
            await cc.w_stream.write(dwadd.as_bytes)

            await cc.checksum(sha1, 0x20, cc.size - 0x20)
            await cc.write_checksum(sha1, cc.size - 0x20)
            # endian swap the checksum
            await cc.r_stream.seek(cc.size - 0x20)
            chks = bytearray(await cc.r_stream.read(20))
            cc.ES32(chks)
            await cc.w_stream.seek(cc.size - 0x20)
            await cc.w_stream.write(chks)

            # now run encryption routine
            cc.set_ptr(0x20)
            while await cc.read():
                cc.ES32()
                cc.encrypt(blowfish_ecb)
                cc.ES32()
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_Rev2.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_Rev2.encrypt_file(filepath)

    @staticmethod
    def reregion_get_new_name(title_id: str) -> str:
        return title_id

