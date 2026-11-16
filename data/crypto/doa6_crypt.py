import os
from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from typing import Iterable, Callable, Any

class Crypt_DoA6:
    NAME_LEN = 32

    @staticmethod
    def derive_key_iv(name: str) -> tuple[bytes, bytes]:
        try:
            r = name.encode("ascii")
        except UnicodeEncodeError:
            raise CryptoError("Invalid save!")
        if len(r) > Crypt_DoA6.NAME_LEN:
            raise CryptoError("Invalid save!")
        r = r.ljust(Crypt_DoA6.NAME_LEN, b"\x00")
        r = CC.hashlib.md5(r).digest()

        non_chars, chars = Crypt_DoA6.partition(r.hex().upper(), lambda x: x not in ("A", "B", "C", "D", "E", "F"))
        key = "".join(non_chars + chars).encode("ascii")

        odd, even = Crypt_DoA6.partition(r, lambda x: x % 2 != 0)
        iv = bytes(odd + even)

        return (key, iv)

    @staticmethod
    def partition(xs: Iterable[Any], predicate: Callable[[Any], bool]) -> tuple[list[bytes], list[bytes]]:
        a = []
        b = []
        for x in xs:
            if predicate(x):
                a.append(x)
            else:
                b.append(x)
        return (a, b)

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            if cc.size % cc.AES.block_size != 0:
                raise CryptoError("Invalid save!")
            key, iv = Crypt_DoA6.derive_key_iv(os.path.basename(filepath))
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CBC, iv=iv)
            while await cc.read():
                cc.decrypt(aes)
                await cc.write()

        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, cc.size)
            await cc.pkcs7_pad_post(cc.AES.block_size)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            await cc.copy(0, cc.size)
            await cc.pkcs7_pad_pre(cc.AES.block_size)

        async with CC(filepath) as cc:
            key, iv = Crypt_DoA6.derive_key_iv(os.path.basename(filepath))
            aes = cc.create_ctx_aes(key, cc.AES.MODE_CBC, iv=iv)
            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if not is_dec:
                await Crypt_DoA6.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                is_dec = await cc.fraction_byte()
            if is_dec:
                await Crypt_DoA6.encrypt_file(filepath)

