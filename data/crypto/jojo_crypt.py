from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError

class Crypt_JoJo:
    @staticmethod
    async def crypt(cc: CC) -> None:
        PRNG_KEY   = 0x4FC36442
        PRNG_MAGIC = 0x001DA597
        PRNG_C1    = 0x0085C9C2
        PRNG_C2    = 0x010B9384
        PRNG_C3    = 0x01915D46

        s0 = ( (PRNG_MAGIC * PRNG_KEY) & 0xFF_FF_FF_FF ) ^ (    PRNG_KEY >> 5)
        s1 = ( (PRNG_MAGIC *       s0) & 0xFF_FF_FF_FF ) ^ ( ( (s0       >> 5) + PRNG_C1) & 0xFF_FF_FF_FF)
        s2 = ( (PRNG_MAGIC *       s1) & 0xFF_FF_FF_FF ) ^ ( ( (s1       >> 5) + PRNG_C2) & 0xFF_FF_FF_FF)
        s3 = ( (PRNG_MAGIC *       s2) & 0xFF_FF_FF_FF ) ^ ( ( (s2       >> 5) + PRNG_C3) & 0xFF_FF_FF_FF)

        j = 0
        while await cc.read():
            c = cc.chunk
            for i in range(len(c)):
                # prng step every 4 bytes
                if j & 3 == 0:
                    j = 0
                    t = s0 ^ ( (s0 << 11) & 0xFF_FF_FF_FF )
                    s = t ^ s3 ^ (s3 >> 19) ^ (t >> 8)
                    s0, s1, s2, s3 = s1, s2, s3, s
                c[i] ^= (s3 >> (8 * j)) & 0xFF
                j += 1
            await cc.write()

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            await Crypt_JoJo.crypt(cc)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        async with CC(filepath) as cc:
            if self.size < 0x227DE8:
                raise CryptoError("Invalid save!")

            crc = cc.create_ctx_crc32_any(
                poly=0x04C11DB7,
                init=0xFF_FF_FF_FF,
                refin=False,
                refout=False,
                xorout=0xFF_FF_FF_FF
            )
            await cc.checksum(crc, 0, 0x227DE4)
            await cc.write_checksum(crc, 0x227DE4)

            await Crypt_JoJo.crypt(cc)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                dec = await cc.fraction_byte()
            if not dec:
                await Crypt_JoJo.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with CC(filepath) as cc:
                dec = await cc.fraction_byte()
            if dec:
                await Crypt_JoJo.decrypt_file(filepath)

