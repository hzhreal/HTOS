import aiofiles
import hashlib
import struct
from Crypto.Cipher import AES
from data.crypto.common import CustomCrypto as CC
from data.crypto.common import CryptoError

class Crypt_Xeno2:
    SAVE_HEADER_KEY = b"PR]-<Q9*WxHsV8rcW!JuH7k_ug:T5ApX"
    SAVE_HEADER_INITIAL_VALUE = b"_Y7]mD1ziyH#Ar=0"
    SAVE_MAGIC_HEADER = b"H\x89\x01L"
    INTERNAL_KEY_OFFSETS = (0x1c, 0x4c)
    HEADER = b"#SAV"
    
    @staticmethod
    async def encryptFile(filePath: str) -> None:
        async with aiofiles.open(filePath, "rb") as decrypted_file:
            await decrypted_file.seek(-1, 2)
            decrypted_file_sub1 = await decrypted_file.tell() - 0x80

            key_offset = bytearray(await decrypted_file.read(1))[0]
            if key_offset not in Crypt_Xeno2.INTERNAL_KEY_OFFSETS:
                raise CryptoError("KEY OFFSET NOT FOUND!")

            await decrypted_file.seek(key_offset)
            key = await decrypted_file.read(0x20)
            initial_value = await decrypted_file.read(0x10)
            new_key = AES.new(key, AES.MODE_CTR, initial_value=initial_value, nonce=b"")
            await decrypted_file.seek(0)

            enc_header = AES.new(Crypt_Xeno2.SAVE_HEADER_KEY, AES.MODE_CTR, initial_value=Crypt_Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=b"").decrypt(await decrypted_file.read(0x80))
            enc_save = new_key.encrypt(await decrypted_file.read(decrypted_file_sub1) + b"\x00")

        md5_hash = hashlib.md5()
        md5_hash.update(enc_header)
        md5_hash.update(enc_save)

        async with aiofiles.open(filePath, "wb") as encrypted_file_soon:
            await encrypted_file_soon.write(Crypt_Xeno2.SAVE_MAGIC_HEADER)
            await encrypted_file_soon.write(struct.pack("<i", len(enc_save) + len(enc_header) + 0x20))
            await encrypted_file_soon.write(struct.pack("<i", len(enc_save) + len(enc_header)))
            await encrypted_file_soon.write(b"\x00\x00\x00\x00")
            await encrypted_file_soon.write(md5_hash.digest())
            await encrypted_file_soon.write(enc_header)
            await encrypted_file_soon.write(enc_save)

    @staticmethod
    async def decryptFile(folderPath: str) -> None:
        files = await CC.obtainFiles(folderPath)

        for filePath in files:

            async with aiofiles.open(filePath, "rb") as encrypted_file:
                if await encrypted_file.read(4) != Crypt_Xeno2.SAVE_MAGIC_HEADER:
                    raise CryptoError("INCORRECT HEADER!")
                
                await encrypted_file.seek(0x10)
                original_hash = await encrypted_file.read(0x10)

                md5_hash = hashlib.md5()
                md5_hash.update(await encrypted_file.read())
                if md5_hash.digest() != original_hash:
                    raise CryptoError("MD5 HASH MISMATCH!")
                await encrypted_file.seek(0x20)

                dec_header = AES.new(Crypt_Xeno2.SAVE_HEADER_KEY, AES.MODE_CTR, initial_value=Crypt_Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=b"").decrypt(await encrypted_file.read(0x80))
                enc_data_test = await encrypted_file.read(16)

                for key_offset in Crypt_Xeno2.INTERNAL_KEY_OFFSETS:
                    key = dec_header[key_offset:key_offset + 0x20]
                    initial_value = dec_header[key_offset + 0x20:key_offset + (0x20 + 0x10)]
                    new_key = AES.new(key, AES.MODE_CTR, initial_value=initial_value, nonce=b"")
                    test_data = new_key.decrypt(enc_data_test)

                    if test_data.startswith(Crypt_Xeno2.HEADER):
                        break

                else:
                    raise CryptoError("INTERNAL SAVE ENCRYPTION KEY NOT FOUND!")
                    
                await encrypted_file.seek(0x20 + 0x80)
                new_key = AES.new(key, AES.MODE_CTR, initial_value=initial_value, nonce=b"")
                decrypted_save = bytearray(new_key.decrypt(await encrypted_file.read()))
                decrypted_save[-1] = key_offset

            async with aiofiles.open(filePath, "wb") as decrypted_file_soon:
                await decrypted_file_soon.write(dec_header)
                await decrypted_file_soon.write(decrypted_save)
    
    @staticmethod
    async def checkEnc_ps(fileName: str) -> None:
        async with aiofiles.open(fileName, "rb") as savegame:
            header = await savegame.read(len(Crypt_Xeno2.HEADER))

        if header == Crypt_Xeno2.HEADER:
            await Crypt_Xeno2.encryptFile(fileName)
