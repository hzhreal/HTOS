import aiofiles
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint8

class Crypt_Xeno2:
    SAVE_HEADER_KEY = b"PR]-<Q9*WxHsV8rcW!JuH7k_ug:T5ApX"
    SAVE_HEADER_INITIAL_VALUE = b"_Y7]mD1ziyH#Ar=0"
    SAVE_HEADER_SIZE = 0x80
    DEC_MAGIC = b"#SAV"

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            aes_header = cc.AES.new(Crypt_Xeno2.SAVE_HEADER_KEY, cc.AES.MODE_CTR, initial_value=Crypt_Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=bytes())
            await cc.r_stream.seek(0x20)
            header = bytearray(await cc.r_stream.read(Crypt_Xeno2.SAVE_HEADER_SIZE))
            aes_header.decrypt(header, header)
            if header[5] & 0x4:
                key_off = 0x4C
            else:
                key_off = 0x1C
            key = header[key_off:key_off + 0x20]
            iv = header[(key_off + 0x20):(key_off + 0x20) + 0x10]
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CTR, initial_value=iv, nonce=bytes())

            await cc.w_stream.seek(0x20)
            await cc.w_stream.write(header)
            cc.set_ptr(0x20 + Crypt_Xeno2.SAVE_HEADER_SIZE)
            while await cc.read():
                cc.decrypt(aes)
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            aes_header = cc.AES.new(Crypt_Xeno2.SAVE_HEADER_KEY, cc.AES.MODE_CTR, initial_value=Crypt_Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=bytes())
            md5 = cc.create_ctx_md5()

            await cc.r_stream.seek(0x20)
            header = bytearray(await cc.r_stream.read(Crypt_Xeno2.SAVE_HEADER_SIZE))

            # checksum 8
            chks = uint8(0)
            for i in range(5, cc.size // 0x20):
                await cc.r_stream.seek(i * 0x20)
                b = (await cc.r_stream.read(1))[0]
                chks.value += b
            header[0x1A] = chks.value

            if header[5] & 0x4:
                key_off = 0x4C
            else:
                key_off = 0x1C
            key = header[key_off:key_off + 0x20]
            iv = header[(key_off + 0x20):(key_off + 0x20) + 0x10]
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CTR, initial_value=iv, nonce=bytes())
            cc.set_ptr(0x20 + Crypt_Xeno2.SAVE_HEADER_SIZE)
            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

            # checksums 1-7 calculated over encrypted data
            await Crypt_Xeno2.add_checksums(cc, header)

            aes_header.encrypt(header, header)
            await cc.w_stream.seek(0x20)
            await cc.w_stream.write(header)

            # md5 over encrypted data
            await cc.checksum(md5, 0x20, cc.size)
            await cc.write_checksum(md5, 0x10)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(0x20)
                magic = await savegame.read(len(Crypt_Xeno2.DEC_MAGIC))
            if magic != Crypt_Xeno2.DEC_MAGIC:
                await Crypt_Xeno2.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(0x20)
            magic = await savegame.read(len(Crypt_Xeno2.DEC_MAGIC))
        if magic == Crypt_Xeno2.DEC_MAGIC:
            await Crypt_Xeno2.encrypt_file(filepath)

    @staticmethod
    async def add_checksums(cc: CC, header: bytearray) -> None:
        chks = uint8(0)

        # checksum 7
        for i in range(14):
            chks.value += header[0x6 + i]
        header[0x15] = chks.value
        chks.value = 0

        # checksum 6
        for i in range(8):
            chks.value += header[0x1C + (i * 4)]
        header[0x16] = chks.value
        chks.value = 0

        # checksum 5
        for i in range(8):
            chks.value += header[0x4C + (i * 4)]
        header[0x17] = chks.value
        chks.value = 0

        # checksum 4
        for i in range(4):
            chks.value += header[0x3C + (i * 4)]
        header[0x18] = chks.value
        chks.value = 0

        # checksum 3
        for i in range(4):
            chks.value += header[0x6C + (i * 4)]
        header[0x19] = chks.value
        chks.value = 0

        # checksum 2
        for i in range(5, cc.size // 0x20):
            await cc.r_stream.seek(i * 0x20)
            b = (await cc.r_stream.read(1))[0]
            chks.value += b
        header[0x1B] = chks.value
        chks.value = header[0x5]

        # checksum 1
        for i in range(7):
            chks.value += header[0x15 + i]
        header[0x14] = chks.value

