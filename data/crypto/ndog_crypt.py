import aiofiles 
import struct
import hashlib
import hmac
import zlib
import crc32c
import os
from data.crypto.common import CustomCrypto as CC
from typing import Literal

# notes: start 0x08 (0xC for the nathan drake collection & 0x10 for tlou part 2), last 4 bytes is size (4 bytes from 0x08 for tlou part 2), 
# endian swap every 4 bytes before and after crypt for the nathan drake collection

class Crypt_Ndog:
    SECRET_KEY = b"(SH[@2>r62%5+QKpy|g6"
    SHA1_HMAC_KEY = b"xM;6X%/p^L/:}-5QoA+K8:F*M!~sb(WK<E%6sW_un0a[7Gm6,()kHoXY+yI/s;Ba"

    HEADER_TLOU = b"The Last of Us"
    HEADER_UNCHARTED = b"Uncharted"

    START_OFFSET = 0x08 # tlou, uncharted 4 & the lost legacy
    START_OFFSET_TLOU2 = 0x10 # tlou part 2
    START_OFFSET_COL = 0xC # the nathan drake collection

    EXCLUDE = ["ICN-ID"]

    @staticmethod
    def calc_size(data: bytearray | bytes, start_offset: Literal[0x08, 0x10, 0xC]) -> tuple[int, bytes]:
        if start_offset == Crypt_Ndog.START_OFFSET_TLOU2: # 0x10
            size_bytes = data[0x08:0x08 + 4]
            size = struct.unpack("<I", size_bytes)[0]
        else: # 0x08, 0xC
            size_bytes = data[-4:]
            size = struct.unpack("<I", size_bytes)[0]
        return size, size_bytes
    
    @staticmethod
    def input_size(data: bytearray, start_offset: Literal[0x08, 0x10, 0xC], size: bytes) -> bytearray:
        if start_offset == Crypt_Ndog.START_OFFSET or start_offset == Crypt_Ndog.START_OFFSET_COL:
            data[-4:] = size
        return data

    @staticmethod
    def fill_zero(data: bytearray, size: int, start_offset: Literal[0x08, 0x10, 0xC]) -> bytearray:
        # make bytes after hmac sha1 checksum zero
        if start_offset == Crypt_Ndog.START_OFFSET: # 0x08
            for i in range((size - 0xC) + 20, len(data)):
                data[i] = 0
        elif start_offset == Crypt_Ndog.START_OFFSET_TLOU2: #0x10
            for i in range((size - 0x04) + 20, len(data)):
                data[i] = 0
        else: # 0xC
            for i in range((size - 0x08) + 20, len(data)):
                data[i] = 0
        return data

    @staticmethod
    def chks_fix(data: bytearray, size: int, start_offset: Literal[0x08, 0x10, 0xC]) -> bytearray:
        # crc32 checksum
        if start_offset == Crypt_Ndog.START_OFFSET: # 0x08
            crc_bl = struct.unpack("<I", data[0x58C:0x58C + 4])[0]
            crc_data = data[0x58C:0x58C + (crc_bl - 4)]
            crc = zlib.crc32(crc_data)

            crc_offset = 0x588
            hash_sub = 0xC
        elif start_offset == Crypt_Ndog.START_OFFSET_TLOU2: # 0x10
            crc_bl = struct.unpack("<I", data[0x594:0x594 + 4])[0]
            crc_data = data[0x594:0x594 + (crc_bl - 4)]
            crc = crc32c.crc32c(crc_data)

            crc_offset = 0x590
            hash_sub = 0x04
        else: # 0xC
            crc_bl = struct.unpack("<I", data[0x590:0x590 + 4])[0]
            crc_data = data[0x590:0x590 + (crc_bl - 4)]
            crc = zlib.crc32(crc_data)

            crc_offset = 0x58C
            hash_sub = 0x08

        crc_final = struct.pack("<I", crc)
        data[crc_offset:crc_offset + len(crc_final)] = crc_final

        # sha1 hmac checksum
        chks_msg = data[start_offset:start_offset + (size - 0x14)]
        hmac_sha1_hash = hmac.new(Crypt_Ndog.SHA1_HMAC_KEY, chks_msg, hashlib.sha1).digest()
        data[size - hash_sub:(size - hash_sub) + len(hmac_sha1_hash)] = hmac_sha1_hash
        
        return data

    @staticmethod
    async def decryptFile(folderPath: str, start_offset: Literal[0x08, 0x10, 0xC]) -> None:
        files = await CC.obtainFiles(folderPath, Crypt_Ndog.EXCLUDE)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                encrypted_data = bytearray(await savegame.read())
            
            first_bytes = encrypted_data[:start_offset]

            size, size_bytes = Crypt_Ndog.calc_size(encrypted_data, start_offset)
            # remove first static bytes
            encrypted_data = encrypted_data[start_offset:]

            if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
                encrypted_data = CC.ES32(encrypted_data)

            # Pad the data to be a multiple of the block size
            p_encrypted_data, p_len = CC.pad_to_blocksize(encrypted_data, CC.BLOWFISH_BLOCKSIZE)

            decrypted_data = CC.decrypt_blowfish_ecb(p_encrypted_data, Crypt_Ndog.SECRET_KEY)
            if p_len > 0:
                decrypted_data = decrypted_data[:-p_len] # remove padding that we added to avoid exception

            if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
                decrypted_data = CC.ES32(decrypted_data)

            # temp data to nullify bytes after hmac sha1 hash  
            tmp_decrypted_data = bytearray(first_bytes + decrypted_data)
            tmp_decrypted_data = Crypt_Ndog.fill_zero(tmp_decrypted_data, size, start_offset)

            # remove first static bytes
            decrypted_data = tmp_decrypted_data[start_offset:]

            decrypted_data = Crypt_Ndog.input_size(decrypted_data, start_offset, size_bytes) # keep the size
            
            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(start_offset)
                await savegame.write(decrypted_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str, start_offset: Literal[0x08, 0x10, 0xC]) -> None:
        if os.path.basename(fileToEncrypt) in Crypt_Ndog.EXCLUDE:
            return

        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decrypted_data = bytearray(await savegame.read())

        first_bytes = decrypted_data[:start_offset]

        size, size_bytes = Crypt_Ndog.calc_size(decrypted_data, start_offset)
        decrypted_data = Crypt_Ndog.chks_fix(decrypted_data, size, start_offset)

        # remove first static bytes
        decrypted_data = decrypted_data[start_offset:]
        if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
            decrypted_data = CC.ES32(decrypted_data)

        # Pad the data to be a multiple of the block size
        p_decrypted_data, p_len = CC.pad_to_blocksize(decrypted_data, CC.AES_BLOCKSIZE)
        
        encrypted_data = CC.encrypt_blowfish_ecb(p_decrypted_data, Crypt_Ndog.SECRET_KEY)
        if p_len > 0:
            encrypted_data = encrypted_data[:-p_len] # remove padding that we added to avoid exception
        
        if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
            encrypted_data = CC.ES32(encrypted_data)

        # temp data to nullify bytes after hmac sha1 hash
        tmp_encrypted_data = bytearray(first_bytes + encrypted_data)
        tmp_encrypted_data = Crypt_Ndog.fill_zero(tmp_encrypted_data, size, start_offset)

        # remove first static bytes
        encrypted_data = tmp_encrypted_data[start_offset:]

        encrypted_data = Crypt_Ndog.input_size(encrypted_data, start_offset, size_bytes) # keep the size

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(first_bytes + encrypted_data)               

    @staticmethod
    async def checkEnc_ps(fileName: str, start_offset: Literal[0x08, 0x10, 0xC]) -> None:
        if os.path.basename(fileName) in Crypt_Ndog.EXCLUDE:
            return

        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(start_offset)
            header = await savegame.read(len(Crypt_Ndog.HEADER_TLOU))

            await savegame.seek(start_offset)
            header1 = await savegame.read(len(Crypt_Ndog.HEADER_UNCHARTED))
        
        if header == Crypt_Ndog.HEADER_TLOU or header == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encryptFile(fileName, start_offset)

        elif header1 == Crypt_Ndog.HEADER_TLOU or header1 == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encryptFile(fileName, start_offset)
