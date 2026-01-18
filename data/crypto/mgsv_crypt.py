import aiofiles
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_MGSV:
    MGSV_TPP_PS4KEY_CUSA01140 = 0x4131F8BE
    MGSV_TPP_PS4KEY_CUSA01154 = 0x4F36C055
    MGSV_TPP_PS4KEY_CUSA01099 = 0x40FDA272

    MGSV_GZ_PS4KEY_CUSA00218 = 0xEA11D524
    MGSV_GZ_PS4KEY_CUSA00211 = 0xD2225CCB
    MGSV_GZ_PS4KEY_CUSA00225 = 0x697B6E1B

    KEYS = {
        "CUSA01140": {"key": MGSV_TPP_PS4KEY_CUSA01140, "name": "MGSVTPPSaveDataNA"},
        "CUSA01154": {"key": MGSV_TPP_PS4KEY_CUSA01154, "name": "MGSVTPPSaveDataEU"},
        "CUSA01099": {"key": MGSV_TPP_PS4KEY_CUSA01099, "name": "MGSVTPPSaveDataJP"},

        "CUSA00218": {"key": MGSV_GZ_PS4KEY_CUSA00218, "name": "MGSVGZSaveDataNA"},
        "CUSA00211": {"key": MGSV_GZ_PS4KEY_CUSA00211, "name": "MGSVGZSaveDataEU"},
        "CUSA00225": {"key": MGSV_GZ_PS4KEY_CUSA00225, "name": "MGSVGZSaveDataJP"}
    }

    HEADER_TPP = b"SV"
    HEADER_GZ = b"gz"

    class MGSV(CC):
        def __init__(self, filepath: str, title_id: str) -> None:
            super().__init__(filepath)
            self.key = uint32(Crypt_MGSV.KEYS[title_id]["key"])

        def crypt(self) -> None:
            self._prepare_list_write()
            for i in range(len(self.chunk)):
                self.key.value ^= (self.key.value << 13)
                self.key.value ^= (self.key.value >> 7)
                self.key.value ^= (self.key.value << 5)

                self.chunk[i].value ^= self.key.value

    @staticmethod
    def mix_key(length: int, title_id: str) -> int: 
        key = uint32(Crypt_MGSV.KEYS[title_id]["key"])
        for _ in range(length):
            key.value ^= (key.value << 13)
            key.value ^= (key.value >> 7)
            key.value ^= (key.value << 5)
        return key.value

    @staticmethod
    async def decrypt_file(filepath: str, title_id: str) -> None:
        async with Crypt_MGSV.MGSV(filepath, title_id) as cc:
            while await cc.read():
                cc.bytes_to_u32array("little")
                cc.crypt()
                cc.array_to_bytearray()
                await cc.write()

    @staticmethod
    async def encrypt_file(filepath: str, title_id: str) -> None:
        async with Crypt_MGSV.MGSV(filepath, title_id) as cc:
            md5 = cc.create_ctx_md5()
            await cc.checksum(md5, 0x10, cc.size)
            await cc.write_checksum(md5, 0)
            while await cc.read():
                cc.bytes_to_u32array("little")
                cc.crypt()
                cc.array_to_bytearray()
                await cc.write()

    @staticmethod
    async def check_dec_ps(folderpath: str, title_id: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            if not await Crypt_MGSV.header_check(filepath):
                await Crypt_MGSV.decrypt_file(filepath, title_id)

    @staticmethod
    async def check_enc_ps(filepath: str, title_id: str) -> None:
        if await Crypt_MGSV.header_check(filepath):
            await Crypt_MGSV.encrypt_file(filepath, title_id)

    @staticmethod
    async def header_check(filepath: str | None, header: bytes | None = None) -> bool:
        if not header:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(0x10)
                header = await savegame.read(2)
        if header == Crypt_MGSV.HEADER_TPP or header == Crypt_MGSV.HEADER_GZ:
            return True
        return False

    @staticmethod
    async def reregion_change_crypt(folderpath: str, target_titleid: str) -> None:
        files = await CC.obtain_files(folderpath)

        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                await savegame.seek(0x10)
                header_word = await savegame.read(4)
                off = await savegame.tell()
                assert off % 4 == 0

            if await Crypt_MGSV.header_check(None, header_word[:2]):
                await Crypt_MGSV.encrypt_file(filepath, target_titleid)
                continue

            for title_id, _ in Crypt_MGSV.KEYS.items():
                key = Crypt_MGSV.mix_key(off // 4, title_id)
                h = uint32(header_word, "little")
                h.value ^= key
                if await Crypt_MGSV.header_check(None, h.as_bytes[:2]):
                    await Crypt_MGSV.decrypt_file(filepath, title_id)
                    await Crypt_MGSV.encrypt_file(filepath, target_titleid)
                    break

