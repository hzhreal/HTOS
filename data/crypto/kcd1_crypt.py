import struct
import aiofiles
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_KCD1:
    MAX_BLOCKS = 1000

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_KCD1.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            max_blocks = Crypt_KCD1.MAX_BLOCKS
            blocks = 0
            i = 0
            while i < cc.size:
                if blocks >= max_blocks:
                    raise CryptoError("Unsupported save!")

                buf = await cc.ext_read(i, 8)
                i += 8
                comp_size = struct.unpack("<I", buf[:4])[0]
                if comp_size == 0 or i + comp_size > cc.size:
                    break
                decomp_size = struct.unpack("<I", buf[4:])[0]

                zlib = cc.create_ctx_zlib_decompress()
                cc.set_ptr(i)
                l = 0
                while await cc.read(stop_off=i + comp_size):
                    l += await cc.decompress(zlib)
                    if l > decomp_size:
                        raise CryptoError("Invalid save!")
                if l != decomp_size:
                    raise CryptoError("Invalid save!")
                i += comp_size
                blocks += 1
                cc.delete_ctx(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_KCD1.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            size = 0
            while await cc.read():
                zlib = cc.create_ctx_zlib_compress()

                buf = bytes(4) + struct.pack("<I", len(cc.chunk))
                if size + len(buf) > cc.SAVESIZE_MAX:
                    raise CryptoError("Unsupported save!")
                await cc.w_stream.write(buf)

                l = await cc.compress(zlib)
                l += await cc.compress_post(zlib)

                await cc.w_stream.seek(size)
                await cc.w_stream.write(struct.pack("<I", l))
                size = await cc.w_stream.seek(0, 2)

                cc.delete_ctx(zlib)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_KCD1.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(8)
                header = await savegame.read(2)
            enc = CC.is_valid_zlib_header(header)
            if enc:
                await Crypt_KCD1.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_KCD1.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(8)
                header = await savegame.read(2)
            enc = CC.is_valid_zlib_header(header)
            if not enc:
                await Crypt_KCD1.encrypt_file(filepath)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        filtered_files = []
        for path in files:
            if path.lower().endswith(".whs"):
                filtered_files.append(path)
        return filtered_files

    @staticmethod
    def file_check(path: str) -> bool:
        return path.lower().endswith(".whs")

