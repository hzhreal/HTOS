import zlib
import aiofiles
from data.crypto.common import CustomCrypto as CC

class Crypt_RCube:
    @staticmethod
    def namecheck(name: str | list[str]) -> bool | list[str]:
        if isinstance(name, str):
            return name.endswith(".dat")
        elif isinstance(name, list):
            valid = []
            for path in name:
                path_ = str(path)
                if path_.endswith(".dat"):
                    valid.append(path_)
                return valid
        else:
            return False

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)
        files = await Crypt_RCube.namecheck(files)

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
        if not Crypt_RCube.namecheck(fileToEncrypt):
            return

        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            header = await savegame.read(0xC)
            decomp_data = await savegame.read()

        comp_data = zlib.compress(decomp_data)
        
        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(header)
            await savegame.write(comp_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        if not Crypt_RCube.namecheck(fileName):
            return

        null_count = 0
        async with aiofiles.open(fileName, "rb") as savegame:
            data = await savegame.read()
        
        for byte in data:
            if byte == 0:
                null_count += 1

        if null_count >= len(data) / 2:
            await Crypt_RCube.encryptFile(fileName)