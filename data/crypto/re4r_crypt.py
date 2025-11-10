import aiofiles
import mmh3
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_RE4R:
    SECRET_KEY = b"wa9Ui_tFKa_6E_D5gVChjM69xMKDX8QxEykYKhzb4cRNLknpCZUra"
    HEADER = b"DSSSDSSS"
    IV = b"\x00" * CC.BLOWFISH_BLOCKSIZE
    SEED = 0x_FF_FF_FF_FF

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtain_files(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0x10)
                header = await savegame.read(0x10)
                data = await savegame.read()

            ciphertext = header + data

            header = CC.ES32(header)
            header = CC.decrypt_blowfish_ecb(header, Crypt_RE4R.SECRET_KEY)
            header = CC.ES32(header)

            # Pad the data to be a multiple of the block size
            p_ciphertext, p_len = CC.pad_to_blocksize(ciphertext, CC.BLOWFISH_BLOCKSIZE)

            p_ciphertext = CC.ES32(p_ciphertext)
            plaintext = CC.decrypt_blowfish_cbc(p_ciphertext, Crypt_RE4R.SECRET_KEY, Crypt_RE4R.IV)
            plaintext = CC.ES32(plaintext)
            if p_len > 0:
                plaintext = plaintext[:-p_len] # remove padding that we added to avoid exception

            plaintext[:len(header)] = header

            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(0x10)
                await savegame.write(plaintext)

    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            init_header = await savegame.read(0x10)
            header = await savegame.read(0x10)
            data = await savegame.read()

        header = CC.ES32(header)
        header = CC.encrypt_blowfish_ecb(header, Crypt_RE4R.SECRET_KEY)
        header = CC.decrypt_blowfish_cbc(header, Crypt_RE4R.SECRET_KEY, Crypt_RE4R.IV)
        header = CC.ES32(header)

        plaintext = header + data

        # Pad the data to be a multiple of the block size
        p_plaintext, p_len = CC.pad_to_blocksize(plaintext, CC.BLOWFISH_BLOCKSIZE)

        plaintext = CC.ES32(p_plaintext)
        ciphertext = CC.encrypt_blowfish_cbc(plaintext, Crypt_RE4R.SECRET_KEY, Crypt_RE4R.IV)
        ciphertext = bytes(CC.ES32(ciphertext))
        if p_len > 0:
            ciphertext = ciphertext[:-p_len] # remove padding that we added to avoid exception

        ciphertext = ciphertext[:-4]
        csum = uint32(mmh3.hash(init_header + ciphertext, Crypt_RE4R.SEED, False), "little")

        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            await savegame.write(init_header)
            await savegame.write(ciphertext)
            await savegame.write(csum.as_bytes)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x10)
            header = await savegame.read(len(Crypt_RE4R.HEADER))
        if header == Crypt_RE4R.HEADER:
            await Crypt_RE4R.encryptFile(fileName)
