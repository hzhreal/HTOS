import aiofiles
import os
import zlib
import struct
from data.crypto.common import CustomCrypto as CC

class Crypt_Terraria:
    KEY = "h3y_gUyZ".encode("utf-16-le")
    DEC_MAGIC = b"relogic"
    COMP_MAGIC = struct.pack("<I", 0x1AA2227E)
    
    @staticmethod
    def filter_paths(paths: list[str]) -> list[str]:
        filtered_paths = []
        for path in paths:
            if path.endswith(".plr") or path.endswith(".wld"):
                filtered_paths.append(path)
        return filtered_paths
    
    @staticmethod
    def filter_path(path: str) -> bool:
        return path.endswith(".plr") or path.endswith(".wld")

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        unfiltered_files = await CC.obtainFiles(folderPath)
        filtered_files = Crypt_Terraria.filter_paths(unfiltered_files)

        for filePath in filtered_files:
            _, ext = os.path.splitext(filePath)

            async with aiofiles.open(filePath, "rb") as savegame:
                encoded_data = await savegame.read()

            match ext:
                case ".plr":
                    # Pad the data to be a multiple of the block sizee
                    p_encoded_data, p_len = CC.pad_to_blocksize(encoded_data, CC.AES_BLOCKSIZE)

                    decoded_data = CC.decrypt_aes_cbc(p_encoded_data, Crypt_Terraria.KEY, Crypt_Terraria.KEY)
                    if p_len > 0:
                        decoded_data = decoded_data[:-p_len]
                case ".wld":
                    decoded_data = zlib.decompress(encoded_data[0x08:])

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decoded_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        if not Crypt_Terraria.filter_path(fileToEncrypt):
            return
        
        _, ext = os.path.splitext(fileToEncrypt)

        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decoded_data = await savegame.read()

        match ext:
            case ".plr":
                # Pad the data to be a multiple of the block size
                p_decoded_data, p_len = CC.pad_to_blocksize(decoded_data, CC.AES_BLOCKSIZE)

                encoded_data = CC.encrypt_aes_cbc(p_decoded_data, Crypt_Terraria.KEY, Crypt_Terraria.KEY)
                if p_len > 0:
                    encoded_data = encoded_data[:-p_len]
            case ".wld":
                size = struct.pack("<I", len(decoded_data))
                encoded_data = Crypt_Terraria.COMP_MAGIC + size
                encoded_data += zlib.compress(decoded_data)

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(encoded_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        if not Crypt_Terraria.filter_path(fileName):
            return

        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x04)
            magic = await savegame.read(len(Crypt_Terraria.DEC_MAGIC))
        
        if magic == Crypt_Terraria.DEC_MAGIC:
            await Crypt_Terraria.encryptFile(fileName)