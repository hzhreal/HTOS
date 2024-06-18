import hashlib
import aiofiles
from typing import Literal
from data.crypto.common import CustomCrypto as CC

class Crypt_MGSV:
    MGSV_TPP_PS4KEY_CUSA01140 = 0x4131F8BE        
    MGSV_TPP_PS4KEY_CUSA01154 = 0x4F36C055
    MGSV_TPP_PS4KEY_CUSA01099 = 0x332E72A8        

    MGSV_GZ_PS4KEY_CUSA00218 = 0xEA11D524        
    MGSV_GZ_PS4KEY_CUSA00211 = 0xD2225CCB        
    MGSV_GZ_PS4KEY_CUSA00225 = 0xB2D4611B

    KEYS = {
        "CUSA01140": {"key": MGSV_TPP_PS4KEY_CUSA01140, "name": "MGSVTPPSaveDataNA"},
        "CUSA01154": {"key": MGSV_TPP_PS4KEY_CUSA01154, "name": "MGSVTPPSaveDataEU"},
        "CUSA01099": {"key": MGSV_TPP_PS4KEY_CUSA01099, "name": "MGSVTPPSaveDataCK"},

        "CUSA00218": {"key": MGSV_GZ_PS4KEY_CUSA00218, "name": "MGSVGZSaveDataNA"},
        "CUSA00211": {"key": MGSV_GZ_PS4KEY_CUSA00211, "name": "MGSVGZSaveDataEU"},
        "CUSA00225": {"key": MGSV_GZ_PS4KEY_CUSA00225, "name": "MGSVGZSaveDataCK"}
    }

    HEADER_TPP = b"SV"
    HEADER_GZ = b"gz"

    @staticmethod
    def crypt_data(data: list[int], length: int, title_id: Literal["CUSA01140", "CUSA01154", "CUSA01099", "CUSA00218", "CUSA00211", "CUSA00225"]) -> list[int]:
        key = Crypt_MGSV.KEYS[title_id]["key"]

        for i in range(length >> 2):
            key ^= (key << 13) & 0xFF_FF_FF_FF
            key ^= (key >> 7) & 0xFF_FF_FF_FF
            key ^= (key << 5) & 0xFF_FF_FF_FF

            data[i] ^= key
        return data

    @staticmethod
    async def decryptFile(folderPath: str, title_id: Literal["CUSA01140", "CUSA01154", "CUSA01099", "CUSA00218", "CUSA00211", "CUSA00225"]) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                encrypted_data = await savegame.read()

            encrypted_data_u32arr = CC.bytes_to_u32array(encrypted_data, "little")
            decrypted_data_u32arr = Crypt_MGSV.crypt_data(encrypted_data_u32arr, len(encrypted_data), title_id)
            
            decrypted_data = CC.u32array_to_bytearray(decrypted_data_u32arr, "little")

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decrypted_data)

    @staticmethod
    async def encryptFile(fileToEncrypt: str, title_id: Literal["CUSA01140", "CUSA01154", "CUSA01099", "CUSA00218", "CUSA00211", "CUSA00225"]) -> None:
        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            decrypted_data = bytearray(await savegame.read())

        to_hash = decrypted_data[0x10:]
        md5 = hashlib.md5()
        md5.update(to_hash)
        md5_data = md5.digest()
        decrypted_data[:len(md5_data)] = md5_data
        
        decrypted_data_u32arr = CC.bytes_to_u32array(decrypted_data, "little")
        encrypted_data_u32arr = Crypt_MGSV.crypt_data(decrypted_data_u32arr, len(decrypted_data), title_id)

        encrypted_data = CC.u32array_to_bytearray(encrypted_data_u32arr, "little")

        async with open(fileToEncrypt, "wb") as savegame:
            await savegame.write(encrypted_data)

    @staticmethod
    async def checkEnc_ps(fileName: str, title_id: Literal["CUSA01140", "CUSA01154", "CUSA01099", "CUSA00218", "CUSA00211", "CUSA00225"]) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x10)
            header = await savegame.read(2)
        
        if header == Crypt_MGSV.HEADER_TPP or header == Crypt_MGSV.HEADER_GZ:
            await Crypt_MGSV.encryptFile(fileName, title_id)

    @staticmethod
    async def reregion_changeCrypt(folderPath: str, target_titleid: Literal["CUSA01140", "CUSA01154", "CUSA01099", "CUSA00218", "CUSA00211", "CUSA00225"]) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:
        
            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0x10)
                header = await savegame.read(2)
        
            if header == Crypt_MGSV.HEADER_TPP or header == Crypt_MGSV.HEADER_GZ:
                await Crypt_MGSV.encryptFile(filePath, target_titleid)

            else:
                for title_id, _ in Crypt_MGSV.KEYS.items():
                    async with aiofiles.open(filePath, "rb") as savegame:
                        encrypted_data = await savegame.read()
                    
                    encrypted_data_u32arr = CC.bytes_to_u32array(encrypted_data, "little")
                    decrypted_data_u32arr = Crypt_MGSV.crypt_data(encrypted_data_u32arr, len(encrypted_data), title_id)

                    decrypted_data = CC.u32array_to_bytearray(decrypted_data_u32arr, "little")
                    header = decrypted_data[0x10:0x10 + 2]
                    if header == Crypt_MGSV.HEADER_TPP or header == Crypt_MGSV.HEADER_GZ:
                        decrypted_data_u32arr = CC.bytes_to_u32array(decrypted_data, "little")
                        encrypted_data_u32arr = Crypt_MGSV.crypt_data(decrypted_data_u32arr, len(decrypted_data), target_titleid)

                        encrypted_data = CC.u32array_to_bytearray(encrypted_data_u32arr, "little")

                        async with aiofiles.open(filePath, "wb") as savegame:
                            await savegame.write(encrypted_data)
                        
                        break
