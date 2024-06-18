import aiofiles
import hashlib
from data.crypto.common import CustomCrypto as CC

class Crypt_SMT5:
    SECRET_KEY = bytes([
		0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66,
		0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66
	])

    MAGIC = b"GVAS"

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:
            
            async with aiofiles.open(filePath, "rb") as savegame:
                encrypted_data = await savegame.read()

            p_encrypted_data, p_len = CC.pad_to_blocksize(encrypted_data, CC.AES_BLOCKSIZE)

            decrypted_data = CC.decrypt_aes_ecb(p_encrypted_data, Crypt_SMT5.SECRET_KEY)
            if p_len > 0:
                decrypted_data = decrypted_data[:-p_len]

            async with aiofiles.open(filePath, "wb") as savegame:
                await savegame.write(decrypted_data)
    
    @staticmethod
    async def encryptFile(fileToEncrypt: str) -> None:
        async with aiofiles.open(fileToEncrypt, "rb") as savegame:
            decrypted_data = bytearray(await savegame.read())

        # patch sha1 checksum
        msg = hashlib.sha1(decrypted_data[0x40:0x40 + (len(decrypted_data) - 0x40) * 8])
        chks = msg.digest()
        decrypted_data[:len(chks)] = chks

        p_decrypted_data, p_len = CC.pad_to_blocksize(decrypted_data, CC.AES_BLOCKSIZE)

        encrypted_data = CC.encrypt_aes_ecb(p_decrypted_data, Crypt_SMT5.SECRET_KEY)
        if p_len > 0:
            encrypted_data = encrypted_data[:-p_len]

        async with aiofiles.open(fileToEncrypt, "wb") as savegame:
            await savegame.write(encrypted_data)

    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            await savegame.seek(0x40)
            magic = await savegame.read(len(Crypt_SMT5.MAGIC))
        
        if magic == Crypt_SMT5.MAGIC:
            await Crypt_SMT5.encryptFile(fileName)