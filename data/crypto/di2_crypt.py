import struct
import aiofiles
import os
import zstandard as zstd
from .common import CustomCrypto, CryptoError

class Crypt_DI2:
    ZSTD_MAGIC = 0xFD2FB528
    
    # this is a header from a save that will get applied when compressing
    # the header contains metadata such as game version
    # we cant really tell that from only the decompressed save
    # so here is one already from a save
    HEADER_FROM_SAVE = b"\xBF\xF5\x0F\x00\x0A\x00\x03\x00\x01\xD9\x0E\x51\x05\x00\x00\x00\x5A\x73\x74\x64\x00\x6E\x20\x00\x00\x00\x00\x01\x00"

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = CustomCrypto.obtainFiles(folderPath)

        for fileName in files:
            filePath = os.path.join(folderPath, fileName)

            async with aiofiles.open(filePath, "rb") as savegame:
                data = await savegame.read()

            start_off = data.find(struct.pack("<I", Crypt_DI2.ZSTD_MAGIC))
            if start_off == -1:
                raise CryptoError("Save is not compressed!")
            
            compressed_data = data[start_off:]
            decompressed_data = zstd.decompress(compressed_data)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decompressed_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decompressed_data = await savegame.read()
        
        compressed_data = zstd.compress(decompressed_data)
        compressed_data = Crypt_DI2.HEADER_FROM_SAVE + compressed_data

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(compressed_data)
    
    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        
        start_off = data.find(struct.pack("<I", Crypt_DI2.ZSTD_MAGIC))
        if start_off == -1:
            await Crypt_DI2.encryptFile(fileName)