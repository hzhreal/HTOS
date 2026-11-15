from data.crypto.common import CustomCrypto as CC

class Crypt_DCUniverse:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not Crypt_DCUniverse.file_check(filepath):
            return

        async with CC(filepath) as cc:
            sha1 = cc.create_ctx_sha1()
            timestamp = await cc.ext_read(0x10, 4)
            await cc.checksum(sha1, 0x14, cc.size)
            await cc.write_checksum(sha1, 0)
            await cc.ext_write(0x10, timestamp)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_DCUniverse.files_check(files)
        for filepath in files:
            await Crypt_DCUniverse.encrypt_file(filepath)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        filtered_files = []
        for path in files:
            if path.lower().endswith("profile.bin"):
                filtered_files.append(path)
        return filtered_files

    @staticmethod
    def file_check(path: str) -> bool:
        return path.lower().endswith("profile.bin")

