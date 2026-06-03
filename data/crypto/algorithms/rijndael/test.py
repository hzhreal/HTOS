import sys
from os.path import dirname as dn
rootdir = dn(dn(dn(dn(dn(__file__)))))
sys.path.append(rootdir)

from os import urandom
from Crypto.Cipher import AES
from data.crypto.algorithms.rijndael.rijndael import Rijndael

def test() -> None:
    for keysize in (16, 24, 32):
        key = urandom(keysize)
        data = urandom(1 << 20)
        iv = urandom(16)

        # ecb
        a = AES.new(key, AES.MODE_ECB).encrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_ECB, 16).encrypt(b, b)
        assert a == b

        a = AES.new(key, AES.MODE_ECB).decrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_ECB, 16).decrypt(b, b)
        assert a == b

        # cbc
        a = AES.new(key, AES.MODE_CBC, iv).encrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_CBC, 16, iv).encrypt(b, b)
        assert a == b

        a = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_CBC, 16, iv).decrypt(b, b)
        assert a == b

        # ctr
        a = AES.new(key, AES.MODE_CTR, initial_value=iv, nonce=b"").encrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_CTR, 16, iv).encrypt(b, b)
        assert a == b

        a = AES.new(key, AES.MODE_CTR, initial_value=iv, nonce=b"").decrypt(data)
        b = bytearray(data)
        Rijndael(key, Rijndael.MODE_CTR, 16, iv).decrypt(b, b)
        assert a == b

if __name__ == "__main__":
    test()

