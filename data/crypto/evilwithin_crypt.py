import os
from data.crypto.common import CustomCrypto as CC

class Crypt_EvilWithin:
    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        if not Crypt_EvilWithin.file_check(filepath):
            return
        basename = os.path.basename(filepath).lower()
        if not "instance" in basename:
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_decompress(wbits=-15)
            while await cc.read(stop_off=cc.size - 4):
                await cc.decompress(zlib)
            await cc.copy(cc.size - 4, cc.size)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_EvilWithin.file_check(filepath):
            return
        basename = os.path.basename(filepath)

        if "instance" in basename:
            async with CC(filepath, in_place=False) as cc:
                zlib = cc.create_ctx_zlib_compress(wbits=-15)
                while await cc.read(stop_off=cc.size - 4):
                    await cc.compress(zlib)
                await cc.compress_post(zlib)
                await cc.copy(cc.size - 4, cc.size)

            async with CC(filepath) as cc:
                md5 = cc.create_ctx_md5()

                blocks, r = divmod(cc.size - 4, 0x2_00_00)
                if r != 0:
                    start = blocks
                else:
                    start = blocks - 1
                start *= 0x2_00_00

                await cc.checksum(md5, start, cc.size - 4)
                d = cc._get_ctx(md5).obj.digest()
                d = bytes(d[i] ^ d[i + 4] ^ d[i + 8] ^ d[i + 12] for i in range(4))
                await cc.ext_write(cc.size - 4, d)
        else:
            async with CC(filepath) as cc:
                md5 = cc.create_ctx_md5()
                await cc.checksum(md5, 4, cc.size)
                d = cc._get_ctx(md5).obj.digest()
                d = bytes(d[i] ^ d[i + 4] ^ d[i + 8] ^ d[i + 12] for i in range(4))
                d = d[::-1]
                await cc.ext_write(0, d)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_EvilWithin.files_check(files)
        for filepath in files:
            basename = os.path.basename(filepath)
            if not "instance" in basename.lower():
                continue
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte(div=4)
            if not is_dec:
                await Crypt_EvilWithin.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_EvilWithin.files_check(files)
        for filepath in files:
            basename = os.path.basename(filepath)
            if not "instance" in basename.lower():
                await Crypt_EvilWithin.encrypt_file(filepath)
                continue
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte(div=4)
            if is_dec:
                await Crypt_EvilWithin.encrypt_file(filepath)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        filtered_files = []
        for path in files:
            basename = os.path.basename(path).lower()
            if basename.endswith(".zwei") or basename == "details":
                filtered_files.append(path)
        return filtered_files

    @staticmethod
    def file_check(path: str) -> bool:
        basename = os.path.basename(path).lower()
        return basename.endswith(".zwei") or basename == "details"

