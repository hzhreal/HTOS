from data.crypto.common import CustomCrypto as CC

class Crypt_RCube:
    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_RCube.files_check(files)

        for filepath in files:
            async with CC(filepath, in_place=False) as cc:
                zlib = cc.create_ctx_zlib_decompress()
                header = await cc.r_stream.read(0xC)
                await cc.w_stream.write(header)
                cc.set_ptr(0xC)
                while await cc.read():
                    await cc.decompress(zlib)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_RCube.file_check(filepath):
            return

        async with CC(filepath, in_place=False) as cc:
            zlib = cc.create_ctx_zlib_compress()
            header = await cc.r_stream.read(0xC)
            await cc.w_stream.write(header)
            cc.set_ptr(0xC)
            while await cc.read():
                await cc.compress(zlib)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if not Crypt_RCube.file_check(filepath):
            return

        async with CC(filepath) as cc:
            is_dec = await cc.fraction_byte()
        if is_dec:
            await Crypt_RCube.encrypt_file(filepath)

    @staticmethod
    def file_check(filepath: str) -> bool:
        return filepath.endswith(".dat")

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        valid = []
        for path in files:
            if path.endswith(".dat"):
                valid.append(path)
        return valid

