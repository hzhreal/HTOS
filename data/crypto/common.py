import os
from Crypto.Cipher import AES

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