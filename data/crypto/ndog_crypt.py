import os
import aiofiles 
import struct
import hashlib
import hmac
import zlib
from .common import CustomCrypto
from Crypto.Cipher import Blowfish
from typing import Literal

# notes: start 0x08 (0xC for the nathan drake collection), last 4 bytes is size, 
# endian swap every 4 bytes before and after crypt for the nathan drake collection

class Crypt_Ndog:
    SECRET_KEY = b"(SH[@2>r62%5+QKpy|g6"
    SHA1_HMAC_KEY = b"xM;6X%/p^L/:}-5QoA+K8:F*M!~sb(WK<E%6sW_un0a[7Gm6,()kHoXY+yI/s;Ba"

    HEADER_TLOU = b"The Last of Us"
    HEADER_UNCHARTED = b"Uncharted"

    START_OFFSET = 0x08 # tlou, uncharted 4 & the lost legacy
    START_OFFSET_COL = 0xC # the nathan drake collection

    @staticmethod
    def fill_zero(data: bytearray, size: int, start_offset: Literal[0x08, 0xC]) -> bytearray:
        # make bytes after hmac sha1 checksum zero
        if start_offset == Crypt_Ndog.START_OFFSET: # 0x08
            for i in range((size - Crypt_Ndog.START_OFFSET_COL) + 20, len(data)):
                data[i] = 0
        else: # 0xC
            for i in range((size - Crypt_Ndog.START_OFFSET) + 20, len(data)):
                data[i] = 0
        return data

    @staticmethod
    def chks_fix(data: bytearray, size: int, start_offset: Literal[0x08, 0xC]) -> bytearray:
        # crc32 checksum
        if start_offset == Crypt_Ndog.START_OFFSET: # 0x08
            crc_bl = struct.unpack("<I", data[0x58C:0x58C + 4])[0]
            crc_data = data[0x58C:0x58C + (crc_bl - 4)]
            crc_offset = 0x588
            other_start_offset = Crypt_Ndog.START_OFFSET_COL
        else: # 0xC
            crc_bl = struct.unpack("<I", data[0x590:0x590 + 4])[0]
            crc_data = data[0x590:0x590 + (crc_bl - 4)]
            crc_offset = 0x58C
            other_start_offset = Crypt_Ndog.START_OFFSET

        crc = zlib.crc32(crc_data)
        crc_final = struct.pack("<I", crc)
        data[crc_offset:crc_offset + len(crc_final)] = crc_final

        # sha1 hmac checksum
        chks_msg = data[start_offset:start_offset + (size - 0x14)]
        hmac_sha1_hash = hmac.new(Crypt_Ndog.SHA1_HMAC_KEY, chks_msg, hashlib.sha1).digest()
        data[size - other_start_offset:(size - other_start_offset) + len(hmac_sha1_hash)] = hmac_sha1_hash
        print(hmac_sha1_hash.hex())
        print(crc_final.hex())
        return data

    @staticmethod
    async def decryptFile(folderPath: str, start_offset: Literal[0x08, 0xC]) -> None:
        exclude = ["ICN-ID"]
        files = CustomCrypto.obtainFiles(folderPath, exclude)

        for fileName in files:
            filePath = os.path.join(folderPath, fileName)

            async with aiofiles.open(filePath, "rb") as savegame:
                first_bytes = await savegame.read(start_offset)
                await savegame.seek(start_offset)
                encrypted_data = await savegame.read()

            dsize = struct.unpack("<I", encrypted_data[-4:])[0]
            new_dsize = struct.pack("<I", dsize)

            if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
                encrypted_data = CustomCrypto.ES32(encrypted_data)

            # Pad the data to be a multiple of the block size
            block_size = Blowfish.block_size
            padding = b"\x00" * (block_size - len(encrypted_data) % block_size)
            padded_data = encrypted_data + padding

            decrypted_data = bytearray(CustomCrypto.decrypt_blowfish_ecb(padded_data, Crypt_Ndog.SECRET_KEY))
            decrypted_data = decrypted_data[:-len(padding)] # remove padding that we added to avoid exception

            if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
                decrypted_data = CustomCrypto.ES32(decrypted_data)

            # temp data to nullify bytes after hmac sha1 hash  
            tmp_decrypted_data = bytearray(first_bytes + decrypted_data)
            tmp_decrypted_data = Crypt_Ndog.fill_zero(tmp_decrypted_data, dsize, start_offset)

            # remove first static bytes
            decrypted_data = tmp_decrypted_data[start_offset:]

            decrypted_data[-4:] = new_dsize # keep the size

            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(start_offset)
                await savegame.write(decrypted_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str, start_offset: Literal[0x08, 0xC]) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decrypted_data = bytearray(await savegame.read())

        first_bytes = decrypted_data[:start_offset]

        dsize = struct.unpack("<I", decrypted_data[-4:])[0]
        new_dsize = struct.pack("<I", dsize)

        decrypted_data = Crypt_Ndog.chks_fix(decrypted_data, dsize, start_offset)

        # remove first static bytes
        decrypted_data = decrypted_data[start_offset:]
        if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
            decrypted_data = CustomCrypto.ES32(decrypted_data)

        # Pad the data to be a multiple of the block size
        block_size = Blowfish.block_size
        padding = b"\x00" * (block_size - len(decrypted_data) % block_size)
        padded_data = decrypted_data + padding
        
        encrypted_data = bytearray(CustomCrypto.encrypt_blowfish_ecb(padded_data, Crypt_Ndog.SECRET_KEY))
        encrypted_data = encrypted_data[:-len(padding)] # remove padding that we added to avoid exception
        
        if start_offset == Crypt_Ndog.START_OFFSET_COL: # 0xC
            encrypted_data = CustomCrypto.ES32(encrypted_data)

        # temp data to nullify bytes after hmac sha1 hash
        tmp_encrypted_data = bytearray(first_bytes + encrypted_data)
        tmp_encrypted_data = Crypt_Ndog.fill_zero(tmp_encrypted_data, dsize, start_offset)

        # remove first static bytes
        encrypted_data = tmp_encrypted_data[start_offset:]

        encrypted_data[-4:] = new_dsize # keep the size

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(first_bytes + encrypted_data)                 

    @staticmethod
    async def checkEnc_ps(fileName: str, start_offset: Literal[0x08, 0xC]) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(start_offset)
            header = await savegame.read(len(Crypt_Ndog.HEADER_TLOU))

            await savegame.seek(start_offset)
            header1 = await savegame.read(len(Crypt_Ndog.HEADER_UNCHARTED))
        
        if header == Crypt_Ndog.HEADER_TLOU or header == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encryptFile(fileName, start_offset)

        elif header1 == Crypt_Ndog.HEADER_TLOU or header1 == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encryptFile(fileName, start_offset)
