from os.path import basename, splitext
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32

class Crypt_PoPersia:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_PoPersia.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress(wbits=-15)
            await cc.copy(0, 0x43C)
            cc.set_ptr(0x43C)
            while await cc.read(stop_off=cc.size - 8):
                await cc.decompress(zlib)
            await cc.copy(cc.size - 8, cc.size)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_PoPersia.file_check(filepath):
            return

        async with CC(filepath) as cc:
            json_len = cc.size - 0x43C - 0x15
            if json_len < 0:
                raise CryptoError("Invalid save!")
            json_len = uint32(json_len, "little")
            await cc.ext_write(0x43C + 0x11, json_len.as_bytes)
            decomp_len = uint32(json_len.value + 0x15, "little").as_bytes
            await cc.ext_write(0x422, decomp_len)
        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress(wbits=-15)
            await cc.copy(0, 0x43C)
            cc.set_ptr(0x43C)
            while await cc.read(stop_off=cc.size - 8):
                await cc.compress(zlib)
            await cc.copy(cc.size - 8, cc.size)
            size = await cc.w_stream.tell()
            comp_len = uint32(size - 0x43C + 0xA, "little").as_bytes
            await cc.w_stream.seek(0x42A)
            await cc.w_stream.write(comp_len)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_PoPersia.files_check(files)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if not is_dec:
                await Crypt_PoPersia.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_PoPersia.files_check(files)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_printable_chars()
            if is_dec:
                await Crypt_PoPersia.encrypt_file(filepath)

    @staticmethod
    def file_check(filepath: str) -> bool:
        filename = basename(filepath)
        if not filename.startswith("PopSaveGameSlot"):
            return False
        return splitext(filename)[1] == ".AlkSave"

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        valid = []
        for path in files:
            if Crypt_PoPersia.file_check(path):
                valid.append(path)
        return valid

