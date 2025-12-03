from data.crypto.common import CustomCrypto as CC

class Crypt_RGG:
    KEY = b"fuEw5rWN8MBS"

    class RGG(CC):
        def __init__(self, filepath: str) -> None:
            super().__init__(filepath)
            self.i = 0

        def xor(self) -> None:
            self._prepare_write()
            for j in range(len(chunk)):
                self.chunk[j] ^= Crypt_RGG.KEY[self.i % len(Crypt_RGG.KEY)]
                self.i += 1

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with Crypt_RGG.RGG(filepath) as cc:
                while await cc.read(stop_off=cc.size - 0x10):
                    cc.xor()
                    await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with Crypt_RGG.RGG(filepath) as cc:
            crc32 = cc.create_ctx_crc32()
            await cc.checksum(crc32, end_off=cc.size - 0x10)
            await cc.write_checksum(crc32, cc.size - 8)

            while await cc.read(stop_off=cc.size - 0x10):
                cc.xor()
                await cc.write()

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with CC(filepath) as cc:
            is_dec = await cc.fraction_byte()
        if is_dec:
            await Crypt_RGG.encrypt_file(filepath)

