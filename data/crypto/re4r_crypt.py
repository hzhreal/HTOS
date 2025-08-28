import aiofiles
from os.path import basename
from data.crypto.common import CryptoError
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint64, uint32

class Crypt_RE4R:
    SECRET_KEY = b""
    HEADER = b"DSSSDSSS"

    @staticmethod
    def xor_down(d: bytearray) -> bytearray:
        size = len(d) // 4
        l_ = 0
        r_ = 0
        for i in range(size):
            l = uint32(d[i:i + 4], "little")
            r = uint32(d[i + 4:i + 8], "little")

            buf = l.as_bytes + r.as_bytes
            buf = CC.decrypt_blowfish_ecb(buf, Crypt_RE4R.SECRET_KEY)

            d[i:i + 4] = uint32(uint32(buf[:4], "little").value ^ l_).as_bytes
            d[i + 4:i + 8] = uint32(uint32(buf[4:8], "little").value ^ r_).as_bytes
            l_ = l.value
            r_ = r.value
        return d

    @staticmethod
    def xor_up(d: bytearray) -> bytearray:
        size = len(d) // 4
        l_ = 0
        r_ = 0
        for i in range(size):
            l = uint32(d[i:i + 4], "little")
            r = uint32(d[i + 4:i + 8], "little")

            buf = bytearray(8)
            buf[:4] = uint32(l.value ^ l_).as_bytes
            buf[4:8] = uint32(r.value ^ r_).as_bytes

            d[i:i + 8] = CC.encrypt_blowfish_ecb(buf, Crypt_RE4R.SECRET_KEY)

            l_ = l.value
            r_ = r.value
        return d

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0x10)
                header = await savegame.read(0x10)
                ciphertext = await savegame.read()

            header = CC.ES32(header)
            header = CC.decrypt_blowfish_ecb(header, Crypt_RE4R.SECRET_KEY)
            header = CC.ES32(header)

            # Pad the data to be a multiple of the block size
            p_ciphertext, p_len = CC.pad_to_blocksize(ciphertext, CC.BLOWFISH_BLOCKSIZE)
            plaintext = Crypt_RE4R.xor_down(bytearray(p_ciphertext))
            if p_len > 0:
                plaintext = plaintext[:-p_len] # remove padding that we added to avoid exception

            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(0x10)
                await savegame.write(header)
                await savegame.write(plaintext)

    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            await savegame.seek(0, 2)
            size = await savegame.tell()
            size -= 8
            if size <= 0:
                raise CryptoError(f"File is to small ({basename(fileToEncrypt)})!")
            await savegame.seek(0)

            await savegame.seek(0x10)
            header = await savegame.read(0x10)

            plaintext = await savegame.read(size - 0x10 - 0x10)

        header = CC.ES32(header)
        header = CC.encrypt_blowfish_ecb(header, Crypt_RE4R.SECRET_KEY)
        header = CC.ES32(header)

        # Pad the data to be a multiple of the block size
        p_plaintext, p_len = CC.pad_to_blocksize(plaintext, CC.BLOWFISH_BLOCKSIZE)
        ciphertext = Crypt_RE4R.xor_up(bytearray(p_plaintext))
        if p_len > 0:
            ciphertext = ciphertext[:-p_len] # remove padding that we added to avoid exception

        csum = uint64(0, "little")

        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            await savegame.seek(0x10)
            await savegame.write(header)
            await savegame.write(ciphertext)
            await savegame.write(csum.as_bytes)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x10)
            header = await savegame.read(len(Crypt_RE4R.HEADER))
        if header == Crypt_RE4R.HEADER:
            await Crypt_RE4R.encryptFile(fileName)
