import aiofiles
import hashlib
from data.crypto.common import CustomCrypto as CC

class Crypt_DSR:
    KEY = bytes([
        0x20, 0xEC, 0x4B, 0x75,
        0x19, 0xC2, 0xBD, 0x15,
        0xE7, 0x0C, 0x1E, 0xE4,
        0xB2, 0x04, 0xB8, 0xCB
    ])
    IV = b"\x00" * 16

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0, 2)
                size = await savegame.tell()
                await savegame.seek(0)
                iv = await savegame.read(16)
                ciphertext = await savegame.read(size - 32)
            
            plaintext = CC.decrypt_aes_cbc(ciphertext, Crypt_DSR.KEY, iv)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(plaintext)

    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            plaintext = await savegame.read()
        
        ciphertext = CC.encrypt_aes_cbc(plaintext, Crypt_DSR.KEY, Crypt_DSR.IV)
        out = Crypt_DSR.IV + ciphertext
        chks = hashlib.md5(out).digest()

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(out)
            await savegame.write(chks)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        if CC.fraction_byte(data):
            await Crypt_DSR.encryptFile(fileName)