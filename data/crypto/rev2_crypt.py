import aiofiles
import hashlib
from data.crypto.common import CustomCrypto as CC

# notes: start at 0x20

class Crypt_Rev2:
    SECRET_KEY = b"zW$2eWaHNdT~6j86T_&j"

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as savegame:
                await savegame.seek(0x20)
                encrypted_data = await savegame.read()

            # endian swap before
            encrypted_data = CC.ES32(encrypted_data)
            
            # Pad the data to be a multiple of the block size
            p_encrypted_data, p_len = CC.pad_to_blocksize(encrypted_data, CC.BLOWFISH_BLOCKSIZE)

            decrypted_data = CC.decrypt_blowfish_ecb(p_encrypted_data, Crypt_Rev2.SECRET_KEY)
            if p_len > 0:
                decrypted_data = decrypted_data[:-p_len] # remove padding that we added to avoid exception

            # endian swap after
            decrypted_data = CC.ES32(decrypted_data)

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
        chks = CC.ES32(chks)

        decrypted_data[length - 0x20:(length - 0x20) + len(chks)] = chks

        # endian swap before
        decrypted_data = CC.ES32(decrypted_data)

        # Pad the data to be a multiple of the block size
        p_decrypted_data, p_len = CC.pad_to_blocksize(decrypted_data, CC.BLOWFISH_BLOCKSIZE)

        encrypted_data = CC.encrypt_blowfish_ecb(p_decrypted_data, Crypt_Rev2.SECRET_KEY)
        if p_len > 0:
            encrypted_data = encrypted_data[:-p_len] # remove padding that we added to avoid exception

        # endian swap after
        encrypted_data = CC.ES32(encrypted_data)

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
