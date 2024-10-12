import zlib
import aiofiles
from data.crypto.common import CustomCrypto as CC

class Crypt_RCube:
    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:
            async with aiofiles.open(filePath, "rb") as savegame:
                header = await savegame.read(0xC)
                comp_data = await savegame.read()
            
            decomp_data = zlib.decompress(comp_data)

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(header)
                await savegame.write(decomp_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            header = await savegame.read(0xC)
            decomp_data = await savegame.read()

        comp_data = zlib.compress(decomp_data)
        
        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(header)
            await savegame.write(comp_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        null_count = 0
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        
        for byte in data:
            if byte == 0:
                null_count += 1

        if null_count >= len(data) / 2:
            await Crypt_RCube.encryptFile(fileName)