import os
from Crypto.Cipher import AES, Blowfish
from typing import Literal

class CryptoError(Exception):
    """Exception raised for errors relating to decrypting or encrypting."""
    def __init__(self, message: str) -> None:
        self.message = message

class CustomCrypto:
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
    def bytes_to_u32array(data: bytes | bytearray, byteorder: Literal["little", "big"]) -> list[int]:
        u32_array = []
        for i in range(0, len(data), 4):
            val = int.from_bytes(data[i:i + 4], byteorder=byteorder, signed=False)
            u32_array.append(val)
        return u32_array
    
    @staticmethod
    def u32array_to_bytearray(data: list[int], byteorder: Literal["little", "big"]) -> bytearray:
        new_array = bytearray()
        for u32_val in data:
            byte_val = u32_val.to_bytes(4, byteorder=byteorder, signed=False)
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
    def obtainFiles(folder: str, exclude: list[str] | None = None) -> list[str]:
        files = []
        if exclude is None:
            exclude = []

        filelist = os.listdir(folder)

        for file in filelist:
            if file != "sce_sys" and file not in exclude:
                files.append(file)

        return files
