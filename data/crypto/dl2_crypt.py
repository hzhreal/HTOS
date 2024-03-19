import aiofiles
import gzip
import os
from .common import CustomCrypto

class Crypt_DL2:
    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = CustomCrypto.obtainFiles(folderPath)

        for fileName in files:
            filePath = os.path.join(folderPath, fileName)

            async with aiofiles.open(filePath, "rb") as savegame:
                compressed_data = await savegame.read()

            uncompressed_data = gzip.decompress(compressed_data)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(uncompressed_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            uncompressed_data = await savegame.read()

        compressed_data = gzip.compress(uncompressed_data)

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(compressed_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            magic = await savegame.read(3)
        
        if magic != b"\x1F\x8B\x08":
            await Crypt_DL2.encryptFile(fileName)
