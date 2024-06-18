import zlib
import aiofiles
import struct
from data.crypto.common import CustomCrypto as CC

class Crypt_RGG:
    KEY = b"fuEw5rWN8MBS"

    @staticmethod
    def xor_data(data: bytearray, size: int) -> bytearray:
        keyLen = len(Crypt_RGG.KEY)
        for i in range(size):
            data[i] ^= Crypt_RGG.KEY[i % keyLen]
        return data
    
    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                encrypted_data = bytearray(await savegame.read())
            size = len(encrypted_data)
            
            decrypted_data = Crypt_RGG.xor_data(encrypted_data, size - 0x10)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decrypted_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decrypted_data = bytearray(await savegame.read())
        size = len(decrypted_data)
        
        chks_data = decrypted_data[:-0x10]
        chks = zlib.crc32(chks_data)
        chks_final = struct.pack("<I", chks)

        decrypted_data[size - 8:(size - 8) + len(chks_final)] = chks_final
        encrypted_data = Crypt_RGG.xor_data(decrypted_data, size - 0x10)
        
        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(encrypted_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        null_count = 0
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        
        for byte in data:
            if byte == 0:
                null_count += 1

        if null_count >= len(data) / 2:
            await Crypt_RGG.encryptFile(fileName)