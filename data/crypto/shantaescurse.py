from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_ShantaeSCurse:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress(wbits=-15)
            await cc.copy(0, 4)
            cc.set_ptr(4)
            while await cc.read():
                await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress(wbits=-15)
            await cc.copy(0, 4)
            cc.set_ptr(4)
            while await cc.read():
                await cc.compress(zlib)
        async with CC(filepath) as cc:
            jhash = cc.create_ctx_jhash_lookup2()
            await cc.checksum(jhash, 4, cc.size)
            digest_obj = cc._get_ctx(jhash).obj
            checksum = uint32(digest_obj.digest(), "little")
            checksum.value += 0x4900DC7C
            await cc.ext_write(0, checksum.as_bytes)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_ShantaeSCurse.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_ShantaeSCurse.encrypt_file(filepath)

