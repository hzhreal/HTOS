import struct
import aiofiles
from data.crypto.common import CustomCrypto as CC
from data.crypto.common import CryptoError
from typing import Literal

class Crypt_BL3:
    SAVEGAME_STRING_BL3 = "OakSaveGame"
    PROFILE_STRING_BL3 = "BP_DefaultOakProfile_C"

    SAVEGAME_STRING_TTWL = "BPSaveGame_Default_C"
    PROFILE_STRING_TTWL = "OakProfile"

    COMMON = b"Player"

    PS4_PROFILE_PREFIX_MAGIC = bytearray([
        0xad, 0x1e, 0x60, 0x4e, 0x42, 0x9e, 0xa9, 0x33, 0xb2, 0xf5, 0x01, 0xe1, 0x02, 0x4d, 0x08, 0x75,
        0xb1, 0xad, 0x1a, 0x3d, 0xa1, 0x03, 0x6b, 0x1a, 0x17, 0xe6, 0xec, 0x0f, 0x60, 0x8d, 0xb4, 0xf9
    ])

    PS4_PROFILE_XOR_MAGIC = bytearray([
        0xba, 0x0e, 0x86, 0x1d, 0x58, 0xe1, 0x92, 0x21, 0x30, 0xd6, 0xcb, 0xf0, 0xd0, 0x82, 0xd5, 0x58,
        0x36, 0x12, 0xe1, 0xf6, 0x39, 0x44, 0x88, 0xea, 0x4e, 0xfb, 0x04, 0x74, 0x07, 0x95, 0x3a, 0xa2
    ])

    PS4_PREFIX_MAGIC = bytearray([
        0xd1, 0x7b, 0xbf, 0x75, 0x4c, 0xc1, 0x80, 0x30, 0x37, 0x92, 0xbd, 0xd0, 0x18, 0x3e, 0x4a, 0x5f,
        0x43, 0xa2, 0x46, 0xa0, 0xed, 0xdb, 0x2d, 0x9f, 0x56, 0x5f, 0x8b, 0x3d, 0x6e, 0x73, 0xe6, 0xb8
    ])

    PS4_XOR_MAGIC = bytearray([
        0xfb, 0xfd, 0xfd, 0x51, 0x3a, 0x5c, 0xdb, 0x20, 0xbb, 0x5e, 0xc7, 0xaf, 0x66, 0x6f, 0xb6, 0x9a,
        0x9a, 0x52, 0x67, 0x0f, 0x19, 0x5d, 0xd3, 0x84, 0x15, 0x19, 0xc9, 0x4a, 0x79, 0x67, 0xda, 0x6d
    ])

    PC_PROFILE_PREFIX_MAGIC = bytearray([
        0xD8, 0x04, 0xB9, 0x08, 0x5C, 0x4E, 0x2B, 0xC0,
        0x61, 0x9F, 0x7C, 0x8D, 0x5D, 0x34, 0x00, 0x56,
        0xE7, 0x7B, 0x4E, 0xC0, 0xA4, 0xD6, 0xA7, 0x01,
        0x14, 0x15, 0xA9, 0x93, 0x1F, 0x27, 0x2C, 0x8F
    ])

    PC_PROFILE_XOR_MAGIC = bytearray([
        0xE8, 0xDC, 0x3A, 0x66, 0xF7, 0xEF, 0x85, 0xE0,
        0xBD, 0x4A, 0xA9, 0x73, 0x57, 0x99, 0x30, 0x8C,
        0x94, 0x63, 0x59, 0xA8, 0xC9, 0xAE, 0xD9, 0x58,
        0x7D, 0x51, 0xB0, 0x1E, 0xBE, 0xD0, 0x77, 0x43
    ])

    PC_PREFIX_MAGIC = bytearray([
        0x71, 0x34, 0x36, 0xB3, 0x56, 0x63, 0x25, 0x5F,
        0xEA, 0xE2, 0x83, 0x73, 0xF4, 0x98, 0xB8, 0x18,
        0x2E, 0xE5, 0x42, 0x2E, 0x50, 0xA2, 0x0F, 0x49,
        0x87, 0x24, 0xE6, 0x65, 0x9A, 0xF0, 0x7C, 0xD7
    ])

    PC_XOR_MAGIC = bytearray([
        0x7C, 0x07, 0x69, 0x83, 0x31, 0x7E, 0x0C, 0x82,
        0x5F, 0x2E, 0x36, 0x7F, 0x76, 0xB4, 0xA2, 0x71,
        0x38, 0x2B, 0x6E, 0x87, 0x39, 0x05, 0x02, 0xC6,
        0xCD, 0xD8, 0xB1, 0xCC, 0xA1, 0x33, 0xF9, 0xB6
    ])

    KEYS_PROFILE = {
        "ps4": {
            "pre": PS4_PROFILE_PREFIX_MAGIC,
            "xor": PS4_PROFILE_XOR_MAGIC
        },
        "pc": {
            "pre": PC_PROFILE_PREFIX_MAGIC,
            "xor": PC_PROFILE_XOR_MAGIC
        }
    }

    KEYS_SAVEGAME = {
        "ps4": {
            "pre": PS4_PREFIX_MAGIC,
            "xor": PS4_XOR_MAGIC
        },
        "pc": {
            "pre": PC_PREFIX_MAGIC,
            "xor": PC_XOR_MAGIC
        }
    }

    IDENTIFIER_STRIGNS = {
        "BL3": {
            "profile": PROFILE_STRING_BL3,
            "savegame": SAVEGAME_STRING_BL3
        },
        "TTWL": {
            "profile": PROFILE_STRING_TTWL,
            "savegame": SAVEGAME_STRING_TTWL
        }
    }

    @staticmethod
    def __searchData(data: bytearray, search: bytes, length: int) -> int:
        for i in range(len(data) - length):
            if data[i: i + length] == search:
                return i
        
        return -1
    
    @staticmethod
    def __encryptData(buffer: bytearray, length: int, PrefixMagic: bytearray, XorMagic: bytearray) -> bytearray:
        for i in range(length):
            b = PrefixMagic[i] if i < 32 else buffer[i - 32]
            b ^= XorMagic[i % 32]
            buffer[i] ^= b

        return buffer

    @staticmethod
    def __decryptData(buffer: bytearray, length: int, PrefixMagic: bytearray, XorMagic: bytearray) -> bytearray:
        for i in range(length - 1, -1, -1):
            b = PrefixMagic[i] if i < 32 else buffer[i - 32]
            b ^= XorMagic[i % 32]
            buffer[i] ^= b

        return buffer

    @staticmethod
    async def decryptFile(folderPath: str, platform: Literal["ps4", "pc"], ttwl: bool) -> None:
        files = await CC.obtainFiles(folderPath)
        game = "TTWL" if ttwl else "BL3"
        profile_string = Crypt_BL3.IDENTIFIER_STRIGNS[game]["profile"]
        savegame_string = Crypt_BL3.IDENTIFIER_STRIGNS[game]["savegame"]

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as encrypted_file:
                encrypted_data = bytearray(await encrypted_file.read())

            if (offset := Crypt_BL3.__searchData(encrypted_data, profile_string.encode("utf-8"), len(profile_string))) > 0:
                pre = Crypt_BL3.KEYS_PROFILE[platform]["pre"]
                xor = Crypt_BL3.KEYS_PROFILE[platform]["xor"]
            elif (offset := Crypt_BL3.__searchData(encrypted_data, savegame_string.encode("utf-8"), len(savegame_string))) > 0:
                pre = Crypt_BL3.KEYS_SAVEGAME[platform]["pre"]
                xor = Crypt_BL3.KEYS_SAVEGAME[platform]["xor"]
            else:
                raise CryptoError("Invalid save!")
            
            offset += len(encrypted_data[offset:].split(b"\x00", 1)[0]) + 1
            size = struct.unpack("<I", encrypted_data[offset: offset + 4])[0]
            offset += 4

            decrypted_data = Crypt_BL3.__decryptData(encrypted_data[offset: offset + size], size, pre, xor)

            async with aiofiles.open(filePath, "r+b") as decrypted_file_soon:
                await decrypted_file_soon.seek(offset)
                await decrypted_file_soon.write(decrypted_data)

    @staticmethod
    async def encryptFile(filePath: str, platform: Literal["ps4", "pc"], ttwl: bool) -> None:
        game = "TTWL" if ttwl else "BL3"
        profile_string = Crypt_BL3.IDENTIFIER_STRIGNS[game]["profile"]
        savegame_string = Crypt_BL3.IDENTIFIER_STRIGNS[game]["savegame"]

        async with aiofiles.open(filePath, "rb") as decrypted_file:
            decrypted_data = bytearray(await decrypted_file.read())

        if (offset := Crypt_BL3.__searchData(decrypted_data, profile_string.encode("utf-8"), len(profile_string))) > 0:
            pre = Crypt_BL3.KEYS_PROFILE[platform]["pre"]
            xor = Crypt_BL3.KEYS_PROFILE[platform]["xor"]
        elif (offset := Crypt_BL3.__searchData(decrypted_data, savegame_string.encode("utf-8"), len(savegame_string))) > 0:
            pre = Crypt_BL3.KEYS_SAVEGAME[platform]["pre"]
            xor = Crypt_BL3.KEYS_SAVEGAME[platform]["xor"]
        else:
            raise CryptoError("Invalid save!")
        
        offset += len(decrypted_data[offset:].split(b"\x00", 1)[0]) + 1
        size = struct.unpack("<I", decrypted_data[offset: offset + 4])[0]
        offset += 4

        encrypted_data = Crypt_BL3.__encryptData(decrypted_data[offset: offset + size], size, pre, xor)

        async with aiofiles.open(filePath, "r+b") as encrypted_file_soon:
            await encrypted_file_soon.seek(offset)
            await encrypted_file_soon.write(encrypted_data)

    @staticmethod
    async def checkEnc_ps(fileName: str, ttwl: bool) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
           data = await savegame.read()

        if Crypt_BL3.searchData(data, Crypt_BL3.COMMON): 
            await Crypt_BL3.encryptFile(fileName, "ps4", ttwl)
           
    @staticmethod
    def searchData(data: bytes | bytearray, search: bytes) -> bool:
        return data.find(search) != -1
