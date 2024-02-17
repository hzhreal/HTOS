from Crypto.Cipher import AES
import os
import aiofiles
import hashlib
import struct
import re

class CryptoError(Exception):
    """Exception raised for errors relating to decrypting or encrypting."""
    def __init__(self, message: str) -> None:
        self.message = message

class CustomCrypto:

    @staticmethod
    def encrypt_aes_ecb(plaintext: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted_data = cipher.encrypt(plaintext)
        return encrypted_data
    
    @staticmethod
    def decrypt_aes_ecb(ciphertext: bytes, key: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted_data = cipher.decrypt(ciphertext)
        return decrypted_data
    
    @staticmethod
    def obtainFiles(folder: str) -> list:
        # File details
        files = []
        filelist = os.listdir(folder)
        for file in filelist:
            if file != "sce_sys":
                files.append(file)

        return files
    
    class Rstar:
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

        @staticmethod 
        def calculate_checksum(data: bytes) -> int:
            checksum = 0x3fac7125

            for char in data:
                char = (char + 128) % 256 - 128 # casting to signed char
                checksum = ((char + checksum) * 0x401) & 0xFFFFFFFF
                checksum = (checksum >> 6 ^ checksum) & 0xFFFFFFFF
            checksum = (checksum*9) & 0xFFFFFFFF
            
            return ((checksum >> 11 ^ checksum) * 0x8001) & 0xFFFFFFFF

        @staticmethod
        async def encryptFile(fileToEncrypt: str, start_offset: int) -> None:
            if start_offset == 0x114 or start_offset == 0x120: key = CustomCrypto.Rstar.PS4_KEY
            else: key = CustomCrypto.Rstar.PC_KEY

            # Read the entire plaintext data from the file
            async with aiofiles.open(fileToEncrypt, "r+b") as file:
                data_before = await file.read(start_offset)  # Read data before the encrypted part
                await file.seek(start_offset)  # Move the file pointer to the start_offset
                data_to_encrypt = await file.read()  # Read the part to encrypt

                # checksum handling
                for chunk in [m.start() for m in re.finditer(b"CHKS\x00", data_to_encrypt)]: # calculate checksums for each chunk
                    await file.seek(start_offset + chunk + 4, 0) # 4 bytes for the magic CHKS
                    header_size = struct.unpack('>I', await file.read(4))[0]
                    data_length = struct.unpack('>I', await file.read(4))[0]
                    await file.seek(header_size - 4 - 4 - 4,1) # 4 for the header size num, 4 for the data length num and 4 for the checksum

                    await file.seek(-data_length, 1)
                    data_to_be_hashed = bytearray(await file.read(data_length))

                    chks_offset = len(data_to_be_hashed) - header_size + (4 + 4)
                    data_to_be_hashed[chks_offset:chks_offset + (4 + 4)] = b"\x00" * (4 + 4) # remove the length and hash
                    new_hash = struct.pack('>I', CustomCrypto.Rstar.calculate_checksum(data_to_be_hashed))
                    
                    await file.seek(start_offset + chunk + (4 + 4 + 4), 0) # 4 bytes for header size num, 4 bytes for the data length and 4 bytes for the checksum
                    await file.write(new_hash)
                
                await file.seek(start_offset)
                data_to_encrypt = await file.read()

            # Pad the data to be a multiple of the block size
            block_size = AES.block_size
            padded_data = data_to_encrypt + b"\x00" * (block_size - len(data_to_encrypt) % block_size)

            # Encrypt the data
            encrypted_data = CustomCrypto.encrypt_aes_ecb(padded_data, key)

            # Combine all the parts and save the new encrypted data to a new file (e.g., "encrypted_SGTA50000")
            async with aiofiles.open(fileToEncrypt, "wb") as encrypted_file:
                await encrypted_file.write(data_before)
                await encrypted_file.write(encrypted_data)

        @staticmethod
        async def decryptFile(upload_decrypted: str, start_offset: int) -> None:
            files = CustomCrypto.obtainFiles(upload_decrypted)
            if start_offset == 0x114 or start_offset == 0x120: key = CustomCrypto.Rstar.PS4_KEY
            else: key = CustomCrypto.Rstar.PC_KEY

            for file_target in files:

                file_name = os.path.join(upload_decrypted, file_target)

                # Read the entire ciphertext data from the file
                async with aiofiles.open(file_name, "rb") as file:
                    data_before = await file.read(start_offset)  # Read data before the encrypted part
                    await file.seek(start_offset)  # Move the file pointer to the start_offset
                    data_to_decrypt = await file.read()  # Read the part to decrypt
                    
                # Pad the data to be a multiple of the block size
                block_size = AES.block_size
                padded_data = data_to_decrypt + b"\x00" * (block_size - len(data_to_decrypt) % block_size)

                # Decrypt the data
                decrypted_data = CustomCrypto.decrypt_aes_ecb(padded_data, key)

                # Save the decrypted data to a new file (e.g., "decrypted_SGTA50000")
                async with aiofiles.open(file_name, "wb") as decrypted_file:
                    await decrypted_file.write(data_before)
                    await decrypted_file.write(decrypted_data)

    class Xeno2:
        SAVE_HEADER_KEY = b"PR]-<Q9*WxHsV8rcW!JuH7k_ug:T5ApX"
        SAVE_HEADER_INITIAL_VALUE = b"_Y7]mD1ziyH#Ar=0"
        SAVE_MAGIC_HEADER = b"H\x89\x01L"
        INTERNAL_KEY_OFFSETS = (0x1c, 0x4c)
        
        @staticmethod
        async def encryptFile(filePath: str) -> None:
            async with aiofiles.open(filePath, "rb") as decrypted_file:
                await decrypted_file.seek(-1, 2)
                decrypted_file_sub1 = decrypted_file.tell() - 0x80

                key_offset = await decrypted_file.read(1)[0]
                if key_offset not in CustomCrypto.Xeno2.INTERNAL_KEY_OFFSETS:
                    raise CryptoError("KEY OFFSET NOT FOUND!")

                await decrypted_file.seek(key_offset)
                key = await decrypted_file.read(0x20)
                initial_value = await decrypted_file.read(0x10)
                new_key = AES.new(key, AES.MODE_CTR, initial_value=initial_value, nonce=b"")
                await decrypted_file.seek(0)

                enc_header = AES.NEW(CustomCrypto.Xeno2.SAVE_HEADER_KEY, AES.MODE_CTR, initial_value=CustomCrypto.Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=b"").decrypt(await decrypted_file.read(0x80))
                enc_save = new_key.encrypt(decrypted_file.read(decrypted_file_sub1) + b"\x00")

            md5_hash = hashlib.md5()
            md5_hash.update(enc_header)
            md5_hash.update(enc_save)

            async with aiofiles.open(filePath, "wb") as encrypted_file_soon:
                await encrypted_file_soon.write(CustomCrypto.Xeno2.SAVE_MAGIC_HEADER)
                await encrypted_file_soon.write(struct.pack("<i", len(enc_save) + len(enc_header) + 0x20))
                await encrypted_file_soon.write(struct.pack("<i", len(enc_save) + len(enc_header)))
                await encrypted_file_soon.write(b"\x00\x00\x00\x00")
                await encrypted_file_soon.write(md5_hash.digest())
                await encrypted_file_soon.write(enc_header)
                await encrypted_file_soon.write(enc_save)

        @staticmethod
        async def decryptFile(folderPath: str) -> None:
            files = CustomCrypto.obtainFiles(folderPath)

            for fileName in files:
                filePath = os.path.join(folderPath, fileName)

                async with aiofiles.open(filePath, "rb") as encrypted_file:
                    if await encrypted_file.read(4) != CustomCrypto.Xeno2.SAVE_MAGIC_HEADER:
                        raise CryptoError("INCORRECT HEADER!")
                    
                    await encrypted_file.seek(0x10)
                    original_hash = await encrypted_file.read(0x10)

                    md5_hash = hashlib.md5()
                    md5_hash.update(await encrypted_file.read())
                    if md5_hash.digest() != original_hash:
                        raise CryptoError("MD5 HASH MISMATCH!")
                    await encrypted_file.seek(0x20)

                    dec_header = AES.new(CustomCrypto.Xeno2.SAVE_HEADER_KEY, AES.MODE_CTR, initial_value=CustomCrypto.Xeno2.SAVE_HEADER_INITIAL_VALUE, nonce=b"").decrypt(await encrypted_file.read(0x80))
                    enc_data_test = await encrypted_file.read(16)

                    for key_offset in CustomCrypto.Xeno2.INTERNAL_KEY_OFFSETS:
                        key = dec_header[key_offset: key_offset + 0x20]
                        initial_value = dec_header[key_offset + 0x20: key_offset + (0x20 + 0x10)]
                        new_key = AES.new(key, AES.MODE_CTR, initial_value=initial_value, nonce=b"")
                        test_data = new_key.decrypt(enc_data_test)

                        if test_data.startswith(b"#SAV"):
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
    
    class BL3:
        SAVEGAME_STRING = "OakSaveGame"
        PROFILE_STRING = "BP_DefaultOakProfile_C"

        PROFILE_PREFIX_MAGIC = bytearray([
            0xad, 0x1e, 0x60, 0x4e, 0x42, 0x9e, 0xa9, 0x33, 0xb2, 0xf5, 0x01, 0xe1, 0x02, 0x4d, 0x08, 0x75,
            0xb1, 0xad, 0x1a, 0x3d, 0xa1, 0x03, 0x6b, 0x1a, 0x17, 0xe6, 0xec, 0x0f, 0x60, 0x8d, 0xb4, 0xf9
        ])

        PROFILE_XOR_MAGIC = bytearray([
            0xba, 0x0e, 0x86, 0x1d, 0x58, 0xe1, 0x92, 0x21, 0x30, 0xd6, 0xcb, 0xf0, 0xd0, 0x82, 0xd5, 0x58,
            0x36, 0x12, 0xe1, 0xf6, 0x39, 0x44, 0x88, 0xea, 0x4e, 0xfb, 0x04, 0x74, 0x07, 0x95, 0x3a, 0xa2
        ])

        PREFIX_MAGIC = bytearray([
            0xd1, 0x7b, 0xbf, 0x75, 0x4c, 0xc1, 0x80, 0x30, 0x37, 0x92, 0xbd, 0xd0, 0x18, 0x3e, 0x4a, 0x5f,
            0x43, 0xa2, 0x46, 0xa0, 0xed, 0xdb, 0x2d, 0x9f, 0x56, 0x5f, 0x8b, 0x3d, 0x6e, 0x73, 0xe6, 0xb8
        ])

        XOR_MAGIC = bytearray([
            0xfb, 0xfd, 0xfd, 0x51, 0x3a, 0x5c, 0xdb, 0x20, 0xbb, 0x5e, 0xc7, 0xaf, 0x66, 0x6f, 0xb6, 0x9a,
            0x9a, 0x52, 0x67, 0x0f, 0x19, 0x5d, 0xd3, 0x84, 0x15, 0x19, 0xc9, 0x4a, 0x79, 0x67, 0xda, 0x6d
        ])

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
        async def decryptFile(folderPath: str) -> None:
            files = CustomCrypto.obtainFiles(folderPath)

            for fileName in files:
                filePath = os.path.join(folderPath, fileName)

                async with aiofiles.open(filePath, "rb") as encrypted_file:
                    encrypted_data = bytearray(await encrypted_file.read())

                if (offset := CustomCrypto.BL3.__searchData(encrypted_data, CustomCrypto.BL3.PROFILE_STRING.encode(), len(CustomCrypto.BL3.PROFILE_STRING))) > 0:
                    pre = CustomCrypto.BL3.PROFILE_PREFIX_MAGIC
                    xor = CustomCrypto.BL3.PROFILE_XOR_MAGIC
                elif (offset := CustomCrypto.BL3.__searchData(encrypted_data, CustomCrypto.BL3.SAVEGAME_STRING.encode(), len(CustomCrypto.BL3.SAVEGAME_STRING))) > 0:
                    pre = CustomCrypto.BL3.PREFIX_MAGIC
                    xor = CustomCrypto.BL3.XOR_MAGIC
                else:
                    raise CryptoError("Invalid save!")
                
                offset += len(encrypted_data[offset:].split(b"\x00", 1)[0]) + 1
                size = struct.unpack("<I", encrypted_data[offset: offset + 4])[0]
                offset += 4

                decrypted_data = CustomCrypto.BL3.__decryptData(encrypted_data[offset: offset + size], size, pre, xor)

                async with aiofiles.open(filePath, "r+b") as decrypted_file_soon:
                    await decrypted_file_soon.seek(offset)
                    await decrypted_file_soon.write(decrypted_data)

        @staticmethod
        async def encryptFile(filePath: str) -> None:
            async with aiofiles.open(filePath, "rb") as decrypted_file:
                decrypted_data = bytearray(await decrypted_file.read())

            if (offset := CustomCrypto.BL3.__searchData(decrypted_data, CustomCrypto.BL3.PROFILE_STRING.encode(), len(CustomCrypto.BL3.PROFILE_STRING))) > 0:
                pre = CustomCrypto.BL3.PROFILE_PREFIX_MAGIC
                xor = CustomCrypto.BL3.PROFILE_XOR_MAGIC
            elif (offset := CustomCrypto.BL3.__searchData(decrypted_data, CustomCrypto.BL3.SAVEGAME_STRING.encode(), len(CustomCrypto.BL3.SAVEGAME_STRING))) > 0:
                pre = CustomCrypto.BL3.PREFIX_MAGIC
                xor = CustomCrypto.BL3.XOR_MAGIC
            else:
                raise CryptoError("Invalid save!")
            
            offset += len(decrypted_data[offset:].split(b"\x00", 1)[0]) + 1
            size = struct.unpack("<I", decrypted_data[offset: offset + 4])[0]
            offset += 4

            encrypted_data = CustomCrypto.BL3.__encryptData(decrypted_data[offset: offset + size], size, pre, xor)

            async with aiofiles.open(filePath, "r+b") as encrypted_file_soon:
                await encrypted_file_soon.seek(offset)
                await encrypted_file_soon(encrypted_data)
        
        @staticmethod
        def searchData(data: bytes, search: bytes) -> bool:
            return data.find(search) != -1
