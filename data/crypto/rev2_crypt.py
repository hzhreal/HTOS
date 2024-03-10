import aiofiles
import os
import hashlib
from .common import CustomCrypto
from Crypto.Cipher import Blowfish

# notes: start at 0x20

class Crypt_Rev2:
    SECRET_KEY = b"zW$2eWaHNdT~6j86T_&j"

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = CustomCrypto.obtainFiles(folderPath)

        for fileName in files:
            filePath = os.path.join(folderPath, fileName)

            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0x20)
                encrypted_data = await savegame.read()

            # endian swap before
            encrypted_data = CustomCrypto.ES32(encrypted_data)
            
            # Pad the data to be a multiple of the block size
            block_size = Blowfish.block_size
            padded_data = encrypted_data + b"\x00" * (block_size - len(encrypted_data) % block_size)

            decrypted_data = CustomCrypto.decrypt_blowfish_ecb(padded_data, Crypt_Rev2.SECRET_KEY)

            # endian swap after
            decrypted_data = CustomCrypto.ES32(decrypted_data)

            async with aiofiles.open(filePath, "r+b") as savegame:
                await savegame.seek(0x20)
                await savegame.write(decrypted_data)

    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            await savegame.seek(0x20)
            decrypted_data = bytearray(await savegame.read())

        length = len(decrypted_data)
        chks_msg = decrypted_data[:length - 0x20]
        sha1 = hashlib.sha1()
        sha1.update(chks_msg)
        chks = sha1.digest()
        
        # endian swap the checksum
        chks = CustomCrypto.ES32(chks)

        decrypted_data[length - 0x20:(length - 0x20) + len(chks)] = chks

        # endian swap before
        decrypted_data = CustomCrypto.ES32(decrypted_data)

        # Pad the data to be a multiple of the block size
        block_size = Blowfish.block_size
        padded_data = decrypted_data + b"\x00" * (block_size - len(decrypted_data) % block_size)

        encrypted_data = CustomCrypto.encrypt_blowfish_ecb(padded_data, Crypt_Rev2.SECRET_KEY)

        # endian swap after
        encrypted_data = CustomCrypto.ES32(encrypted_data)

        async with aiofiles.open(fileToEncrypt, "r+b") as savegame:
            await savegame.seek(0x20)
            await savegame.write(encrypted_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x98)
            stat_val1 = await savegame.read(1)

            await savegame.seek(0x9C)
            stat_val2 = await savegame.read(1)

            await savegame.seek(0xA0)
            stat_val3 = await savegame.read(1)
 
        if stat_val1 == b"d" and stat_val2 == b"d" and stat_val3 == b"d": # not 100 on this one
            await Crypt_Rev2.encryptFile(fileName)