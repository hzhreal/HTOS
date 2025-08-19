import aiofiles
import aiofiles.ospath
import hashlib
import struct
from Crypto.Cipher import AES
from data.crypto.common import CustomCrypto as CC
from data.crypto.common import CryptoError
from utils.type_helpers import uint8

class Crypt_Xeno2:
    SAVE_HEADER_KEY = b"PR]-<Q9*WxHsV8rcW!JuH7k_ug:T5ApX"
    SAVE_HEADER_INITIAL_VALUE = b"_Y7]mD1ziyH#Ar=0"
    SAVE_MAGIC_HEADER = b"H\x89\x01L"
    INTERNAL_KEY_OFFSETS = (0x1c, 0x4c)
    HEADER = b"#SAV"

    @staticmethod
    async def encryptFile(filePath: str) -> None:
        await Crypt_Xeno2.encrypt_file(filePath)
        await Crypt_Xeno2.encryptFile_epilogue(filePath)

    @staticmethod
    async def encrypt_file(filePath: str) -> None:
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
    async def encryptFile_epilogue(filePath: str) -> None:
        async with aiofiles.open(filePath, "rb") as savegame:
            ciphertext = await savegame.read()
        await Crypt_Xeno2.decryptFile(filePath)
        async with aiofiles.open(filePath, "rb") as savegame:
            plaintext = await savegame.read()

        check8 = Crypt_Xeno2.checksum8(plaintext)
        check2 = Crypt_Xeno2.checksum2(ciphertext)
        check3 = Crypt_Xeno2.checksum3(plaintext)
        check4 = Crypt_Xeno2.checksum4(plaintext)
        check5 = Crypt_Xeno2.checksum5(plaintext)
        check6 = Crypt_Xeno2.checksum6(plaintext)
        check7 = Crypt_Xeno2.checksum7(plaintext)

        plaintext[0x15] = check7
        plaintext[0x16] = check6
        plaintext[0x17] = check5
        plaintext[0x18] = check4
        plaintext[0x19] = check3
        plaintext[0x1B] = check2
        plaintext[0x1A] = check8
        plaintext[0x14] = Crypt_Xeno2.checksum1(plaintext)

        async with aiofiles.open(filePath, "wb") as savegame:
            await savegame.write(plaintext)
        await Crypt_Xeno2.encrypt_file(filePath)

    @staticmethod
    async def decryptFile(path: str) -> None:
        if await aiofiles.ospath.isfile(path):
            files = [path]
        else:
            files = await CC.obtainFiles(path)

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

    def calculate_checksum(data: bytes | bytearray, start_offset: int) -> int:
        if start_offset >= len(data):
            raise CryptoError("Invalid save!")
        section2 = data[start_offset:]
        checksum = uint8()
        num_blocks = len(section2) // 0x20
        for i in range(num_blocks):
            checksum.value += section2[i * 0x20]
        return checksum
    
    def checksum1(data: bytes | bytearray) -> int:
        checksum = uint8(
            data[0x05]
            + data[0x15]
            + data[0x16]
            + data[0x17]
            + data[0x18]
            + data[0x19]
            + data[0x1A]
            + data[0x1B]
        )
        return checksum.value

    def checksum2(data: bytes | bytearray) -> int:
        return Crypt_Xeno2.calculate_checksum(data, 0xA0)
    
    def checksum3(data: bytes | bytearray) -> int:
        if len(data) < 0x80:
            raise CryptoError("Invalid save!")
        checksum = uint8(data[0x6C] + data[0x70] + data[0x74] + data[0x78])
        return checksum.value

    def checksum4(data: bytes | bytearray) -> int:
        if len(data) < 0x80:
            raise CryptoError("Invalid save!")
        checksum = uint8(data[0x3C] + data[0x40] + data[0x44] + data[0x48])
        return checksum.value

    def checksum5(data: bytes | bytearray) -> int:
        if len(data) < 0x80:
           raise CryptoError("Invalid save!")
        checksum = uint8()
        for i in range(8):
            checksum += data[0x4C + i * 4]
        return checksum

    def checksum6(data: bytes | bytearray) -> int:
        if len(data) < 0x40:
            raise CryptoError("Invalid save!")
        checksum = uint8()
        for i in range(8):
            checksum += data[0x1C + i * 4]
        return checksum.value

    def checksum7(data: bytes | bytearray) -> int:
        if len(data) < 0x14:
            raise CryptoError("Invalid save!")
        checksum = uint8()
        for i in range(14):
            checksum += data[0x06 + i]
            checksum &= 0xFF
        return checksum.value

    def checksum8(data: bytes | bytearray) -> int:
        return Crypt_Xeno2.calculate_checksum(data, 0x80)