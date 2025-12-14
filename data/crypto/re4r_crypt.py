import aiofiles
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_RE4R:
    SECRET_KEY = b"wa9Ui_tFKa_6E_D5gVChjM69xMKDX8QxEykYKhzb4cRNLknpCZUra"
    HEADER = b"DSSSDSSS"
    SEED = uint32(0x_FF_FF_FF_FF, "little", const=True)

    @staticmethod
    async def decrypt_file(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with CC(filepath) as cc:
                blowfish_ecb = cc.Blowfish.new(Crypt_RE4R.SECRET_KEY, cc.Blowfish.MODE_ECB)
                blowfish_cbc = cc.create_ctx_blowfish(Crypt_RE4R.SECRET_KEY, cc.Blowfish.MODE_CBC, iv=bytes([0] * 8))

                await cc.r_stream.seek(0x10)
                header = bytearray(await cc.r_stream.read(0x10))
                cc.set_ptr(0x10)

                cc.ES32(header)
                blowfish_ecb.decrypt(header, header)
                cc.ES32(header)

                if cc.size - 0x20 > 0 and (cc.size - 0x20) % cc.Blowfish.block_size == 0:
                    n = 8
                else:
                    n = 0

                while await cc.read(stop_off=cc.size - n):
                    cc.ES32()
                    cc.decrypt(blowfish_cbc)
                    cc.ES32()
                    await cc.write()
                await cc.w_stream.seek(0x10)
                await cc.w_stream.write(header)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            blowfish_ecb = cc.Blowfish.new(Crypt_RE4R.SECRET_KEY, cc.Blowfish.MODE_ECB)
            blowfish_cbc = cc.Blowfish.new(Crypt_RE4R.SECRET_KEY, cc.Blowfish.MODE_CBC, bytes([0] * 8))

            await cc.r_stream.seek(0x10)
            header = bytearray(await cc.r_stream.read(0x10))
            cc.set_ptr(0x10)

            cc.ES32(header)
            blowfish_ecb.encrypt(header, header)
            blowfish_cbc.decrypt(header, header)
            cc.ES32(header)
            await cc.w_stream.seek(0x10)
            await cc.w_stream.write(header)

            if cc.size - 0x20 > 0 and (cc.size - 0x20) % cc.Blowfish.block_size == 0:
                n = 8
            else:
                n = 0

            blowfish_cbc = cc.create_ctx_blowfish(Crypt_RE4R.SECRET_KEY, cc.Blowfish.MODE_CBC, iv=bytes([0] * 8))
            mmh3 = cc.create_ctx_mmh3_u32(Crypt_RE4R.SEED)
            while await cc.read(stop_off=cc.size - n):
                cc.ES32()
                cc.encrypt(blowfish_cbc)
                cc.ES32()
                await cc.write()
            await cc.checksum(mmh3, 0, cc.size - 4)
            await cc.write_checksum(mmh3, cc.size - 4)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(0x10)
            header = await savegame.read(len(Crypt_RE4R.HEADER))
        if header == Crypt_RE4R.HEADER:
            await Crypt_RE4R.encrypt_file(filepath)
