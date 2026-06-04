from data.crypto.common import CustomCrypto as CC

class Crypt_SWAOFB:
    HMAC_KEY = b"1FB00CC8D8D94CD0A94C847C2F04A921"
    PREFIX = bytes([
        0x00, 0x00, 0x00, 0x00,
        0x14, 0x00, 0x00, 0x00
    ])
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            off = await cc.find(Crypt_SWAOFB.PREFIX, cc.size - 0x1000, cc.size)
            if off == -1:
                return
            await cc.copy(0, off + len(Crypt_SWAOFB.PREFIX))
            hmac_sha1 = cc.create_ctx_hmac(Crypt_SWAOFB.HMAC_KEY, CC.hashlib.sha1)
            await cc.checksum(hmac_sha1, 0, off + 4)
            await cc.write_checksum(hmac_sha1, off + len(Crypt_SWAOFB.PREFIX))

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            await Crypt_SWAOFB.encrypt_file(filepath)

