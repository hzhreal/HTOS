import aiofiles
import struct
import re
from enum import Enum
from typing import Literal
from data.crypto.common import CustomCrypto as CC
from utils.constants import GTAV_TITLEID
from utils.type_helpers import uint32, uint64

class Crypt_Rstar:
    class TitleHashTypes(Enum):
        STANDARD = 0
        DATE = 1

    # GTA V & RDR 2
    PS4_KEY = bytes([
        0x16,  0x85,  0xff,  0xa3,  0x8d,  0x01,  0x0f,  0x0d,
        0xfe,  0x66,  0x1c,  0xf9,  0xb5,  0x57,  0x2c,  0x50,
        0x0d,  0x80,  0x26,  0x48,  0xdb,  0x37,  0xb9,  0xed,
        0x0f,  0x48,  0xc5,  0x73,  0x42,  0xc0,  0x22,  0xf5
    ])

    PC_KEY = bytes([
        0x46,  0xed,  0x8d,  0x3f,  0x94,  0x35,  0xe4,  0xec,
        0x12,  0x2c,  0xb2,  0xe2,  0xaf,  0x97,  0xc5,  0x7e,
        0x4c,  0x5a,  0x8c,  0x30,  0x92,  0xc7,  0x84,  0x4e,
        0x11,  0xc6,  0x86,  0xff,  0x41,  0xdf,  0x41,  0x0f
    ])

    GTAV_PS_HEADER_OFFSET = 0x114
    GTAV_PC_HEADER_OFFSET = 0x108
    GTAV_HEADER = b"PSIN"

    RDR2_PS_HEADER_OFFSET = 0x120
    RDR2_PC_HEADER_OFFSET = 0x110
    RDR2_HEADER = b"RSAV"

    TYPES = {
        GTAV_PS_HEADER_OFFSET: {"key": PS4_KEY, "type": TitleHashTypes.STANDARD},
        RDR2_PS_HEADER_OFFSET: {"key": PS4_KEY, "type": TitleHashTypes.STANDARD},

        GTAV_PC_HEADER_OFFSET: {"key": PC_KEY, "type": TitleHashTypes.STANDARD},
        RDR2_PC_HEADER_OFFSET: {"key": PC_KEY, "type": TitleHashTypes.DATE}
    }

    @staticmethod
    def jooat(data: bytes | bytearray, seed: int = 0x3FAC7125, byteorder: Literal["little", "big"] = "big") -> uint32:
        num = uint32(seed, byteorder)
        for byte in data:
            char = (byte + 128) % 256 - 128  # casting to signed char
            num.value = num.value + char
            num.value = num.value + (num.value << 10)
            num.value = num.value ^ (num.value >> 6)

        num.value = num.value + (num.value << 3)
        num.value = num.value ^ (num.value >> 11)
        num.value = num.value + (num.value << 15)

        return num
    
    @staticmethod
    async def fix_title_chks(savegame: aiofiles.threadpool.binary.AsyncFileIO) -> None:
        """GTA V PS4 & PC, RDR2 PS4"""
        await savegame.seek(0)
        iv = await savegame.read(4) # read the initial data, must be 00 00 00 01 (gta), 00 00 00 04 (rdr2)
        seed_data = iv[::-1] # reverse order
        seed = Crypt_Rstar.jooat(seed_data, 0) # generate seed

        # read title and fix checksum
        title = await savegame.read(0x100)
        chks = Crypt_Rstar.jooat(title, seed.value)
        await savegame.write(chks.as_bytes)

    @staticmethod
    async def fix_date_chks(savegame: aiofiles.threadpool.binary.AsyncFileIO) -> None:
        """RDR2 PC"""
        await savegame.seek(0)
        iv = await savegame.read(4) # read initial data, must be 00 00 00 04
        seed_data = iv[::-1] # reverse order
        seed = Crypt_Rstar.jooat(seed_data, 0) # generate seed

        # read date and fix checksum
        await savegame.seek(0x104)
        date = uint64(await savegame.read(8), "big")
        date.value = CC.ES32(date.as_bytes)
        chks = Crypt_Rstar.jooat(date.as_bytes, seed.value)
        await savegame.write(chks.as_bytes)

    @staticmethod
    async def encryptFile(fileToEncrypt: str, start_offset: Literal[0x114, 0x108, 0x120, 0x110]) -> None:
        key = Crypt_Rstar.TYPES[start_offset]["key"]
        type_ = Crypt_Rstar.TYPES[start_offset]["type"]

        # Read the entire plaintext data from the file
        async with aiofiles.open(fileToEncrypt, "r+b") as file:
            match type_:
                case Crypt_Rstar.TitleHashTypes.STANDARD:
                    # fix title checksum
                    await Crypt_Rstar.fix_title_chks(file)
                    await file.seek(0)
                case Crypt_Rstar.TitleHashTypes.DATE:
                    await Crypt_Rstar.fix_date_chks(file)
                    await file.seek(0)

            data_before = await file.read(start_offset)  # Read data before the encrypted part
            await file.seek(start_offset)  # Move the file pointer to the start_offset
            data_to_encrypt = await file.read()  # Read the part to encrypt

            # checksum handling
            for chunk in [m.start() for m in re.finditer(b"CHKS\x00", data_to_encrypt)]: # calculate checksums for each chunk
                await file.seek(start_offset + chunk + 4, 0) # 4 bytes for the magic CHKS
                header_size = struct.unpack(">I", await file.read(4))[0]
                data_length = struct.unpack(">I", await file.read(4))[0]
                await file.seek(header_size - 4 - 4 - 4, 1) # 4 for the header size num, 4 for the data length num and 4 for the checksum

                await file.seek(-data_length, 1)
                data_to_be_hashed = bytearray(await file.read(data_length))

                chks_offset = len(data_to_be_hashed) - header_size + (4 + 4)
                data_to_be_hashed[chks_offset:chks_offset + (4 + 4)] = b"\x00" * (4 + 4) # remove the length and hash
                new_hash = Crypt_Rstar.jooat(data_to_be_hashed)
                
                await file.seek(start_offset + chunk + (4 + 4 + 4), 0) # 4 bytes for header size num, 4 bytes for the data length and 4 bytes for the checksum
                await file.write(new_hash.as_bytes)
            
            await file.seek(start_offset)
            data_to_encrypt = await file.read()

        # Truncate the data to be a multiple of the block size
        t_decrypted_data = CC.truncate_to_blocksize(data_to_encrypt, CC.AES_BLOCKSIZE)

        # Encrypt the data
        encrypted_data = CC.encrypt_aes_ecb(t_decrypted_data, key)

        # Combine all the parts and save the new encrypted data to a new file (e.g., "encrypted_SGTA50000")
        async with aiofiles.open(fileToEncrypt, "wb") as encrypted_file:
            await encrypted_file.write(data_before)
            await encrypted_file.write(encrypted_data)

    @staticmethod
    async def decryptFile(upload_decrypted: str, start_offset: Literal[0x114, 0x108, 0x120, 0x110]) -> None:
        files = await CC.obtainFiles(upload_decrypted)
        key = Crypt_Rstar.TYPES[start_offset]["key"]

        for file_name in files:

            # Read the entire ciphertext data from the file
            async with aiofiles.open(file_name, "rb") as file:
                data_before = await file.read(start_offset)  # Read data before the encrypted part
                await file.seek(start_offset)  # Move the file pointer to the start_offset
                data_to_decrypt = await file.read()  # Read the part to decrypt
                
            # Pad the data to be a multiple of the block size
            t_encrypted_data = CC.truncate_to_blocksize(data_to_decrypt, CC.AES_BLOCKSIZE)

            # Decrypt the data
            decrypted_data = CC.decrypt_aes_ecb(t_encrypted_data, key)

            # Save the decrypted data to a new file (e.g., "decrypted_SGTA50000")
            async with aiofiles.open(file_name, "wb") as decrypted_file:
                await decrypted_file.write(data_before)
                await decrypted_file.write(decrypted_data)
    
    @staticmethod
    async def checkEnc_ps(fileName: str, title_ids: list[str]) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            if title_ids == GTAV_TITLEID:
                await savegame.seek(Crypt_Rstar.GTAV_PS_HEADER_OFFSET)
                header = await savegame.read(len(Crypt_Rstar.GTAV_HEADER))
    
            else:
                await savegame.seek(Crypt_Rstar.RDR2_PS_HEADER_OFFSET)
                header = await savegame.read(len(Crypt_Rstar.RDR2_HEADER))
        
        match header:
            case Crypt_Rstar.GTAV_HEADER:
                await Crypt_Rstar.encryptFile(fileName, Crypt_Rstar.GTAV_PS_HEADER_OFFSET)
            case Crypt_Rstar.RDR2_HEADER:
                await Crypt_Rstar.encryptFile(fileName, Crypt_Rstar.RDR2_PS_HEADER_OFFSET)
