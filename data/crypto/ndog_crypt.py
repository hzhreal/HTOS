import os
import aiofiles 
import struct
import hashlib
import hmac
import zlib
from .common import CustomCrypto
from Crypto.Cipher import Blowfish

# notes: start 0x08, last 4 bytes is size (without header)

class Crypt_Ndog:
    SECRET_KEY = b"(SH[@2>r62%5+QKpy|g6"
    SHA1_HMAC_KEY = b"xM;6X%/p^L/:}-5QoA+K8:F*M!~sb(WK<E%6sW_un0a[7Gm6,()kHoXY+yI/s;Ba"

    HEADER_TLOU = b"The Last of Us"
    HEADER_UNCHARTED = b"Uncharted"

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        exclude = ["ICN-ID"]
        files = CustomCrypto.obtainFiles(folderPath, exclude)
       
        for fileName in files:
            filePath = os.path.join(folderPath, fileName)
            
            async with aiofiles.open(filePath, "rb") as savegame:
                first_8 = await savegame.read(8)
                await savegame.seek(0x08)
                encrypted_data = await savegame.read()

            dsize = struct.unpack("<I", encrypted_data[-4:])[0]

            # Pad the data to be a multiple of the block size
            block_size = Blowfish.block_size
            padding = b"\x00" * (block_size - len(encrypted_data) % block_size)
            padded_data = encrypted_data + padding

            decrypted_data = bytearray(CustomCrypto.decrypt_blowfish_ecb(padded_data, Crypt_Ndog.SECRET_KEY))
            new_dsize = struct.pack("<I", dsize)

            tmp_decrypted_data = bytearray(first_8 + decrypted_data)

            # make bytes after hmac sha1 checksum zero
            for i in range((dsize - 0xC) + 20, len(tmp_decrypted_data)):
                tmp_decrypted_data[i] = 0

            decrypted_data = tmp_decrypted_data[8:]
            decrypted_data = decrypted_data[:-len(padding)] # remove padding that we added to avoid exception
            decrypted_data[-4:] = new_dsize

            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(0x08)
                await savegame.write(decrypted_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decrypted_data = bytearray(await savegame.read())

        first_8 = decrypted_data[:8]
        dsize = struct.unpack("<I", decrypted_data[-4:])[0]

        # crc32 checksum
        crc_bl = struct.unpack("<I", decrypted_data[0x58C:0x58C + 4])[0]
        crc_data = decrypted_data[0x58C:0x58C + (crc_bl - 4)]
        crc = zlib.crc32(crc_data)
        crc_final = struct.pack("<I", crc)
        decrypted_data[0x588:0x588 + 4] = crc_final

        # sha1 hmac checksum
        chks_msg = decrypted_data[0x08:0x08 + (dsize - 0x14)]
        hmac_sha1_hash = hmac.new(Crypt_Ndog.SHA1_HMAC_KEY, chks_msg, hashlib.sha1).digest()
        decrypted_data[dsize - 0xC:(dsize - 0xC) + len(hmac_sha1_hash)] = hmac_sha1_hash

        # remove first 8 static bytes
        decrypted_data = decrypted_data[8:]

        # Pad the data to be a multiple of the block size
        block_size = Blowfish.block_size
        padding = b"\x00" * (block_size - len(decrypted_data) % block_size)
        padded_data = decrypted_data + padding
        
        encrypted_data = bytearray(CustomCrypto.encrypt_blowfish_ecb(padded_data, Crypt_Ndog.SECRET_KEY))
        new_dsize = struct.pack("<I", dsize)

        encrypted_data = encrypted_data[:-len(padding)] # remove padding that we added to avoid exception
        encrypted_data[-4:] = new_dsize

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(first_8 + encrypted_data)                   

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x08)
            header = await savegame.read(len(Crypt_Ndog.HEADER))
        
        if header == Crypt_Ndog.HEADER_TLOU or header == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encryptFile(fileName)
