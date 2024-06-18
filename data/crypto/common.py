import os
import aiofiles.os
from Crypto.Cipher import AES, Blowfish
from typing import Literal

class CryptoError(Exception):
    """Exception raised for errors relating to decrypting or encrypting."""
    def __init__(self, message: str) -> None:
        self.message = message

class CustomCrypto:
    AES_BLOCKSIZE = AES.block_size
    BLOWFISH_BLOCKSIZE = Blowfish.block_size

    @staticmethod
    def truncate_to_blocksize(data: bytes | bytearray, blocksize: int) -> bytes | bytearray:
        if blocksize <= 0:
            return type(data)()

        size = len(data)
        size_in_range = size & ~(blocksize - 1)

        return data[:size_in_range]
    
    @staticmethod
    def pad_to_blocksize(data: bytes | bytearray, blocksize: int, pad_value: int = 0) -> tuple[bytes | bytearray, int]:
        if blocksize <= 0:
            return type(data)()
        
        size = len(data)
        pad_len = blocksize - (size % blocksize)
        if pad_len == blocksize:
            return data, 0
        
        pad_value &= 0xFF
        return data + bytes([pad_value] * pad_len), pad_len

    @staticmethod
    def encrypt_aes_ecb(plaintext: bytes | bytearray, key: bytes | bytearray) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted_data = cipher.encrypt(plaintext)
        return encrypted_data
    
    @staticmethod
    def decrypt_aes_ecb(ciphertext: bytes | bytearray, key: bytes | bytearray) -> bytes:
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted_data = cipher.decrypt(ciphertext)
        return decrypted_data
    
    @staticmethod
    def encrypt_aes_cbc(plaintext: bytes | bytearray, key: bytes | bytearray, iv: bytes | bytearray) -> bytes:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(plaintext)
        return encrypted_data
    
    @staticmethod
    def decrypt_aes_cbc(ciphertext: bytes | bytearray, key: bytes | bytearray, iv: bytes | bytearray) -> bytes:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(ciphertext)
        return decrypted_data
    
    @staticmethod
    def encrypt_blowfish_ecb(plaintext: bytes | bytearray, key: bytes | bytearray) -> bytes:
        cipher = Blowfish.new(key, Blowfish.MODE_ECB)
        encrypted_data = cipher.encrypt(plaintext)
        return encrypted_data
    
    @staticmethod
    def decrypt_blowfish_ecb(ciphertext: bytes | bytearray, key: bytes | bytearray) -> bytes:
        cipher = Blowfish.new(key, Blowfish.MODE_ECB)
        decrypted_data = cipher.decrypt(ciphertext)
        return decrypted_data
    
    @staticmethod
    def bytes_to_u32array(data: bytes | bytearray, byteorder: Literal["little", "big"], signed: bool = False) -> list[int]:
        u32_array = []
        for i in range(0, len(data), 4):
            val = int.from_bytes(data[i:i + 4], byteorder=byteorder, signed=signed)
            u32_array.append(val)
        return u32_array
    
    @staticmethod
    def u32array_to_bytearray(data: list[int], byteorder: Literal["little", "big"], signed: bool = False) -> bytearray:
        new_array = bytearray()
        for u32_val in data:
            u32_val &= 0xFF_FF_FF_FF
            byte_val = u32_val.to_bytes(4, byteorder=byteorder, signed=signed)
            new_array.extend(byte_val)
        return new_array
    
    @staticmethod
    def ES32(data: bytes | bytearray) -> bytearray:
        swapped_data = bytearray()
        for i in range(0, len(data), 4):
            chunk = data[i:i + 4]
            swapped_chunk = bytearray(reversed(chunk))
            swapped_data.extend(swapped_chunk)
        return swapped_data
     
    @staticmethod
    async def obtainFiles(folder: str, exclude: list[str] | None = None, files: list[str] | None = None) -> list[str]:
        if files is None:
            files = []
        if exclude is None:
            exclude = []

        filelist = await aiofiles.os.listdir(folder)

        for entry in filelist:
            entry_path = os.path.join(folder, entry)

            if await aiofiles.os.path.isfile(entry_path) and entry not in exclude:
                files.append(entry_path)
            elif await aiofiles.os.path.isdir(entry_path) and entry_path != os.path.join(folder, "sce_sys"):
                await CustomCrypto.obtainFiles(entry_path, exclude, files)

        return files