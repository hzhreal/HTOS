import aiofiles 
import os

from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

# notes: start 0x08 (0xC for the nathan drake collection & 0x10 for tlou part 2), last 4 bytes is size (4 bytes from 0x08 for tlou part 2), 
# endian swap every 4 bytes before and after crypt for the nathan drake collection

class Crypt_Ndog:
    SECRET_KEY = b"(SH[@2>r62%5+QKpy|g6"
    HMAC_SHA1_KEY = b"xM;6X%/p^L/:}-5QoA+K8:F*M!~sb(WK<E%6sW_un0a[7Gm6,()kHoXY+yI/s;Ba"

    HEADER_TLOU = b"The Last of Us"
    HEADER_UNCHARTED = b"Uncharted"

    START_OFF = 0x08 # tlou, uncharted 4 & the lost legacy
    START_OFF_TLOU2 = 0x10 # tlou part 2
    START_OFF_COL = 0xC # the nathan drake collection

    EXCLUDE = ["ICN-ID"]

    class Ndog(CC):
        def __init__(self, filepath: str, start_off: int) -> None:
            super().__init__(filepath)
            self.start_off = start_off
            self.dsize = None

        async def get_dsize(self) -> None:
            if self.start_off == Crypt_Ndog.START_OFF_TLOU2:
                await self.r_stream.seek(0x08)
                self.dsize = uint32(await self.r_stream.read(4), "little").value
            else:
                await self.r_stream.seek(self.size - 4)
                self.dsize = uint32(await self.r_stream.read(4), "little").value

        async def chks_fix(self) -> None:
            # crc32
            crc32 = self.create_ctx_crc32()
            if self.start_off == Crypt_Ndog.START_OFF:
                crc_bl_off = 0x58C
                crc_off = 0x588
                hash_sub = 0xC
            elif self.start_off == Crypt_Ndog.START_OFF_TLOU2:
                crc_bl_off = 0x594
                crc_off = 0x590
                hash_sub = 0x4
            else:
                crc_bl_off = 0x590
                crc_off = 0x58C
                hash_sub = 0x8
            await self.r_stream.seek(crc_bl_off)
            crc_bl = uint32(await self.r_stream.read(4), "little").value
            await self.checksum(crc32, crc_bl_off, crc_bl_off + (crc_bl - 4))
            await self.write_checksum(crc32, crc_off)

            # hmac sha1
            hmac_sha1 = self.create_ctx_hmac(Crypt_Ndog.HMAC_SHA1_KEY, self.hashlib.sha1)
            await self.checksum(hmac_sha1, self.start_off, self.dsize - 20)
            await self.write_checksum(sha1, self.dsize - hash_sub)

    @staticmethod
    async def decrypt_file(foldepath: str, start_off: int) -> None:
        files = await CC.obtain_files(foldepath, Crypt_Ndog.EXCLUDE)

        for filepath in files:
            async with Crypt_Ndog.Ndog(filepath, start_off) as cc:
                blowfish = cc.create_ctx_blowfish(Crypt_Ndog.SECRET_KEY, cc.Blowfish.block_size)
                await cc.get_dsize()
                cc.set_ptr(cc.start_off)

                while await cc.read(stop_off=cc.dsize):
                    if cc.start_off == Crypt_Ndog.START_OFF_COL:
                        cc.ES32()
                    await cc.decrypt(blowfish)
                    if cc.start_off == Crypt_Ndog.START_OFF_COL:
                        cc.ES32()

    @staticmethod
    async def encrypt_file(filepath: str, start_off: int) -> None:
        if os.path.basename(filepath) in Crypt_Ndog.EXCLUDE:
            return

        async with Crypt_Ndog.Ndog(filepath, start_off) as cc:
            blowfish = cc.create_ctx_blowfish(Crypt_Ndog.SECRET_KEY, cc.Blowfish.block_size)
            await cc.get_dsize()
            cc.set_ptr(cc.start_off)

            await cc.chks_fix()
            while await cc.read(stop_off=cc.dsize):
                if cc.start_off == Crypt_Ndog.START_OFF_COL:
                    cc.ES32() 
                cc.encrypt(blowfish)
                if cc.start_off == Crypt_Ndog.START_OFF_COL:
                    cc.ES32()

    @staticmethod
    async def check_enc_ps(filepath: str, start_off: int) -> None:
        if os.path.basename(filepath) in Crypt_Ndog.EXCLUDE:
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(start_off)
            header = await savegame.read(len(Crypt_Ndog.HEADER_TLOU))

            await savegame.seek(start_off)
            header1 = await savegame.read(len(Crypt_Ndog.HEADER_UNCHARTED))

        if header == Crypt_Ndog.HEADER_TLOU or header == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encrypt_file(filepath, start_off)
        elif header1 == Crypt_Ndog.HEADER_TLOU or header1 == Crypt_Ndog.HEADER_UNCHARTED:
            await Crypt_Ndog.encrypt_file(filepath, start_off)
