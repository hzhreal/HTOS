import aiofiles
import os
from enum import Enum

from data.crypto.common import CustomCrypto as CC
from data.crypto.exceptions import CryptoError
from utils.type_helpers import uint32, int8

class Crypt_Rstar:
    class TitleHashTypes(Enum):
        STANDARD = 0
        DATE = 1

    # GTA V & RDR 2
    PS4_KEY = bytes([
        0x16,  0x85,  0xFF,  0xA3,  0x8D,  0x01,  0x0F,  0x0D,
        0xFE,  0x66,  0x1C,  0xF9,  0xB5,  0x57,  0x2C,  0x50,
        0x0D,  0x80,  0x26,  0x48,  0xDB,  0x37,  0xB9,  0xED,
        0x0F,  0x48,  0xc5,  0x73,  0x42,  0xC0,  0x22,  0xF5
    ])

    PC_KEY = bytes([
        0x46,  0xED,  0x8D,  0x3F,  0x94,  0x35,  0xE4,  0xEC,
        0x12,  0x2C,  0xB2,  0xE2,  0xAF,  0x97,  0xC5,  0x7E,
        0x4C,  0x5A,  0x8C,  0x30,  0x92,  0xC7,  0x84,  0x4E,
        0x11,  0xC6,  0x86,  0xFF,  0x41,  0xDF,  0x41,  0x0F
    ])

    GTAV_PS_HEADER_OFFSET = 0x114
    GTAV_PC_HEADER_OFFSET = 0x108
    GTAV_HEADER = b"PSIN"

    RDR2_PS_HEADER_OFFSET = 0x120
    RDR2_PC_HEADER_OFFSET = 0x110
    RDR2_HEADER = b"RSAV"

    assert len(GTAV_HEADER) == len(RDR2_HEADER)
    HEADER_SIZE = len(GTAV_HEADER)

    TYPES = {
        GTAV_PS_HEADER_OFFSET: {"key": PS4_KEY, "type": TitleHashTypes.STANDARD},
        RDR2_PS_HEADER_OFFSET: {"key": PS4_KEY, "type": TitleHashTypes.STANDARD},

        GTAV_PC_HEADER_OFFSET: {"key": PC_KEY, "type": TitleHashTypes.STANDARD},
        RDR2_PC_HEADER_OFFSET: {"key": PC_KEY, "type": TitleHashTypes.DATE}
    }

    UNSUPPORTED_FORMATS = ("pgta", "prdr", "profile", "player")

    class Rstar(CC):
        def __init__(self, filepath: str) -> None:
            super().__init__(filepath)

        class jooat:
            def __init__(self, seed: uint32 = uint32(0x3FAC7125, "big", const=True)) -> None:
                self.jooat = uint32(seed.value, seed.ENDIANNESS)

            def update(self, chunk: bytes | bytearray) -> None:
                assert len(chunk) <= CC.CHUNKSIZE

                for byte in chunk:
                    char = int8(byte).value
                    self.jooat.value += char
                    self.jooat.value += (self.jooat.value << 10)
                    self.jooat.value ^= (self.jooat.value >> 6)

            def digest(self) -> bytes:
                self.jooat.value += (self.jooat.value << 3)
                self.jooat.value ^= (self.jooat.value >> 11)
                self.jooat.value += (self.jooat.value << 15)
                return self.jooat.as_bytes

        def create_ctx_jooat(self, seed: uint32 = uint32(0x3FAC7125, "big")) -> int:
            update_obj = Crypt_Rstar.Rstar.jooat(seed)
            return self._create_ctx(update_obj)

        async def fix_title_chks(self) -> None:
            """GTA V PS4 & PC, RDR2 PS4"""
            jooat = Crypt_Rstar.Rstar.jooat(uint32(0, "big"))

            # title seed is jooat of iv with initial seed of 0
            await self.r_stream.seek(0)
            iv = bytearray(await self.r_stream.read(4)) # normally 00 00 00 01 (gta), 00 00 00 04 (rdr2)
            self.ES32(iv)
            jooat.update(iv)
            jooat.digest()

            # read title and fix checksum
            title = await self.r_stream.read(0x100)
            jooat.update(title)
            jooat.digest()
            await self.w_stream.seek(4 + 0x100)
            await self.w_stream.write(jooat.jooat.as_bytes)

        async def fix_date_chks(self) -> None:
            """RDR2 PC"""
            jooat = Crypt_Rstar.Rstar.jooat(uint32(0, "big"))

            # data seed is jooat of iv with initial seed of 0
            await self.r_stream.seek(0)
            iv = bytearray(await self.r_stream.read(4)) # normally 00 00 00 04
            self.ES32(iv)
            jooat.update(iv)
            jooat.digest()

            # read date and fix checksum
            await self.r_stream.seek(0x104)
            date = bytearray(await self.r_stream.read(8))
            self.ES32(date)
            jooat.update(date)
            jooat.digest()
            await self.w_stream.seek(0x104 + 8)
            await self.w_stream.write(jooat.jooat.as_bytes)

    @staticmethod
    async def decrypt_file(filepath: str, start_off: int) -> None:
        if not Crypt_Rstar.file_check(filepath):
            return

        key = Crypt_Rstar.TYPES[start_off]["key"]

        async with CC(filepath) as cc:
            aes = cc.create_ctx_aes(key, cc.AES.MODE_ECB)
            await cc.trim_trailing_bytes(min_required=16 + 1) # remove empty space that autosaves have towards EOF
            cc.set_ptr(start_off)
            while await cc.read():
                cc.decrypt(aes)
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str, start_off: int) -> None:
        if not Crypt_Rstar.file_check(filepath):
            return

        key = Crypt_Rstar.TYPES[start_off]["key"]
        type_ = Crypt_Rstar.TYPES[start_off]["type"]

        async with Crypt_Rstar.Rstar(filepath) as cc:
            aes = cc.create_ctx_aes(key, cc.AES.MODE_ECB)
            await cc.trim_trailing_bytes(min_required=16 + 1) # remove empty space that autosaves have towards EOF
            match type_:
                case Crypt_Rstar.TitleHashTypes.STANDARD:
                    await cc.fix_title_chks()
                case Crypt_Rstar.TitleHashTypes.DATE:
                    await cc.fix_date_chks()

            ptr = start_off
            while True:
                jooat = cc.create_ctx_jooat()
                chks_off = await cc.find(b"CHKS", ptr)
                if chks_off == -1:
                    break

                await cc.r_stream.seek(chks_off + 4)
                header_size = uint32(await cc.r_stream.read(4), "big")
                if header_size.value != 0x14 or chks_off + 0x14 > cc.size:
                    raise CryptoError("Invalid!")
                data_size = uint32(await cc.r_stream.read(4), "big")

                # nullify data size and checksum
                await cc.w_stream.seek(chks_off + 8)
                await cc.w_stream.write(bytes([0] * (4 + 4)))

                chks_start_off = chks_off - data_size.value + header_size.value
                await cc.checksum(jooat, chks_start_off, chks_start_off + data_size.value)
                await cc.write_checksum(jooat, chks_off + (4 + 4 + 4))
                cc.delete_ctx(jooat)

                await cc.w_stream.seek(chks_off + 8)
                await cc.w_stream.write(data_size.as_bytes)

                ptr = chks_off + header_size.value

            cc.set_ptr(start_off)
            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str, start_off: int) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_Rstar.files_check(files)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(start_off)
                header = await savegame.read(Crypt_Rstar.HEADER_SIZE)
            if header != Crypt_Rstar.GTAV_HEADER and header != Crypt_Rstar.RDR2_HEADER:
                await Crypt_Rstar.decrypt_file(filepath, start_off)

    @staticmethod
    async def check_enc_ps(filepath: str, start_off: int) -> None:
        if not Crypt_Rstar.file_check(filepath):
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            await savegame.seek(start_off)
            header = await savegame.read(Crypt_Rstar.HEADER_SIZE)
        if header == Crypt_Rstar.GTAV_HEADER or header == Crypt_Rstar.RDR2_HEADER:
            await Crypt_Rstar.encrypt_file(filepath, start_off)

    @staticmethod
    def file_check(filepath: str) -> bool:
        filename = os.path.basename(filepath).lower()
        return not filename.startswith(Crypt_Rstar.UNSUPPORTED_FORMATS)

    @staticmethod
    def files_check(files: list[str]) -> list[str]:
        valid = []
        for path in files:
            filename = os.path.basename(path).lower()
            if not filename.startswith(Crypt_Rstar.UNSUPPORTED_FORMATS):
                valid.append(path)
        return valid

