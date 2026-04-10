import struct
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32, uint64

class Crypt_AlienIso:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            await cc.r_stream.seek(0x18)
            off1 = uint32(await cc.r_stream.read(4), "little").value
            await cc.r_stream.seek(0x1C)
            off2 = uint32(await cc.r_stream.read(4), "little").value
            off = off1 + off2

            sha1 = cc.create_ctx_sha1()
            await cc.checksum(sha1, 0x20, off)
            sha1_digest_obj = cc._get_ctx(sha1).obj
            digest = sha1_digest_obj.digest()
            a, b, c = struct.unpack("<QQI", digest)
            checksum = uint64(a ^ b ^ c, "little").as_bytes
            await cc.ext_write(0x8, checksum)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        await Crypt_AlienIso.encrypt_file(filepath)

