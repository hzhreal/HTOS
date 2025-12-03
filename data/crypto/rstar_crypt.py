import aiofiles
import os
from enum import Enum

from data.crypto.common import CustomCrypto as CC
from utils.constants import GTAV_TITLEID
from utils.type_helpers import uint32, uint64, int8

class Crypt_Rstar:
    class TitleHashTypes(Enum):
        STANDARD = 0
        DATE = 1

    # GTA V & RDR 2
    PS4_KEY = bytes([
        0x16,  0x85,  0xff,  0xa3,  0x8d,  0x01,  0x0f,  0x0d,
        0xfe,  0x66,  0x1c,  0xf9,  0xb5,  0x57,  0x2c,  0x50,
        0x0d,  0x80,  0x26,  0x48,  0xdb,  0x37,  0xb9,  0xed,
        0x0f,  0x48,  0xc5,  0x73,  0x42,  0xc0,  0x22,  0xf5
    ])

    PC_KEY = bytes([
        0x46,  0xed,  0x8d,  0x3f,  0x94,  0x35,  0xe4,  0xec,
        0x12,  0x2c,  0xb2,  0xe2,  0xaf,  0x97,  0xc5,  0x7e,
        0x4c,  0x5a,  0x8c,  0x30,  0x92,  0xc7,  0x84,  0x4e,
        0x11,  0xc6,  0x86,  0xff,  0x41,  0xdf,  0x41,  0x0f
    ])

    GTAV_PS_HEADER_OFFSET = 0x114
    GTAV_PC_HEADER_OFFSET = 0x108
    GTAV_HEADER = b"PSIN"

    RDR2_PS_HEADER_OFFSET = 0x120
    RDR2_PC_HEADER_OFFSET = 0x110
    RDR2_HEADER = b"RSAV"

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
            def __init__(self, seed: uint32 = uint32(0x3FAC7125, "big")) -> None:
                self.jooat = seed

            def update(self, chunk: bytes | bytearray) -> None:
                assert len(chunk) <= CC.CHUNKSIZE

                for byte in data:
                    char = int8(byte).value
                    self.jooat.value += char
                    self.jooat.value += (self.jooat.value << 10)
                    self.jooat.value ^= (self.jooat.value >> 6)

            def digest(self) -> bytes:
                self.jooat.value += (self.joaat.value << 3)
                self.jooat.value ^= (self.jooat.value >> 11)
                self.jooat.value += (self.jooat.value << 15)
                return self.jooat.as_bytes

        def create_ctx_jooat(self, seed: uint32 = uint32(0x3FAC7125, "big")) -> int:
            update_obj = Crypt_Rstar.jooat(seed)
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
    async def decrypt_file(folderpath: str, start_off: int) -> None:
        files = await CC.obtain_files(folderpath)
        files = Crypt_Rstar.files_check(files)
        key = Crypt_Rstar.TYPES[start_offset]["key"]

        for filepath in files:
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
            jooat = cc.create_ctx_jooat()
            await cc.trim_trailing_bytes(min_required=16 + 1) # remove empty space that autosaves have towards EOF
            match type_:
                case Crypt_Rstar.TitleHashTypes.STANDARD:
                    await cc.fix_title_chks()
                case Crypt_Rstar.TitleHashTypes.DATE:
                    await cc.fix_date_chks()

            ptr = start_off
            while True:
                chks_off = await cc.find(b"CHKS", ptr)
                if chks_off == -1:
                    break

                await cc.r_stream.seek(chks_off + 4)
                header_size = uint32(await r_stream.read(4), "big")
                data_size = uint32(await cc.r_stream.read(4), "big")

                await cc.r_stream.seek(header_size.value - 4 - 4 - 4, 1)
                chks_start_off = await cc.r_stream.seek(-data_size.value, 1)

                # nullify data size and checksum
                await cc.w_stream.seek(chks_off + 8)
                await cc.w_stream.write(bytes([0] * (4 + 4)))

                await cc.checksum(jooat, chks_start_off, chks_start_off + data_size.value)
                await cc.write_checksum(jooat, chks_off + (4 + 4 + 4))

                await cc.w_stream.seek(chks_off + 8)
                await cc.w_stream.write(data_size.as_bytes)

                ptr = chks_off + header_size.value

            cc.set_ptr(start_off)
            while await cc.read():
                cc.encrypt(aes)
                await cc.write()

    @staticmethod
    async def check_enc_ps(filepath: str, title_ids: list[str]) -> None:
        if not Crypt_Rstar.file_check(filepath):
            return

        async with aiofiles.open(filepath, "rb") as savegame:
            if title_ids == GTAV_TITLEID:
                await savegame.seek(Crypt_Rstar.GTAV_PS_HEADER_OFFSET)
                header = await savegame.read(len(Crypt_Rstar.GTAV_HEADER))
            else:
                await savegame.seek(Crypt_Rstar.RDR2_PS_HEADER_OFFSET)
                header = await savegame.read(len(Crypt_Rstar.RDR2_HEADER))

        match header:
            case Crypt_Rstar.GTAV_HEADER:
                await Crypt_Rstar.encrypt_file(filepath, Crypt_Rstar.GTAV_PS_HEADER_OFFSET)
            case Crypt_Rstar.RDR2_HEADER:
                await Crypt_Rstar.encrypt_file(filepath, Crypt_Rstar.RDR2_PS_HEADER_OFFSET)

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

