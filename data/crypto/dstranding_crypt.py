from os.path import basename
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_DStranding:
    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        if not basename(filepath) == "checkpoint.dat":
            return

        async with CC(filepath) as cc:
            md5 = cc.create_ctx_md5()
            await cc.r_stream.seek(0x1FC)
            msg_len = uint32(await cc.r_stream.read(4), "little").value
            await cc.checksum(md5, 0x200, 0x200 + msg_len)
            await cc.write_checksum(md5, 0x1EC)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        if not basename(filepath) == "checkpoint.dat":
            return

        await Crypt_DStranding.encrypt_file(filepath)

