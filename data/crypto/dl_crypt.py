import aiofiles
import gzip
from typing import Literal
from .common import CustomCrypto

# both dying light 1 & 2 uses gzip, also dead island 1

class Crypt_DL:
    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = CustomCrypto.obtainFiles(folderPath)

        for filePath in files:
            
            async with aiofiles.open(filePath, "rb") as savegame:
                compressed_data = await savegame.read()

            uncompressed_data = gzip.decompress(compressed_data)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(uncompressed_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str, version: Literal["DL1", "DL2", "DI1"]) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            uncompressed_data = await savegame.read()

        # checksum handling in the future
        if version == "DL1":
            ...
        elif version == "DL2":
            ...
        else:
            ...

        compressed_data = gzip.compress(uncompressed_data)

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(compressed_data)

    @staticmethod
    async def checkEnc_ps(fileName: str, version: Literal["DL1", "DL2", "DI1"]) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            magic = await savegame.read(3)
        
        if magic != b"\x1F\x8B\x08":
            await Crypt_DL.encryptFile(fileName, version)
