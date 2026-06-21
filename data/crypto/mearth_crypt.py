import aiofiles
from data.crypto.common import CustomCrypto as CC
from utils.type_helpers import uint32

class Crypt_MEarth:
    MAGIC = b"SAVE"
    MAGIC_OFFSETS = (0x00, 0x08)
    SIZE_OFFSETS = {
        0x00: 0x10,
        0x08: 0x14
    }
    WRITE_OFFSETS = {
        0x00: (0x08,),
        0x08: (0x04, 0x10)
    }

    @staticmethod
    async def encrypt_file(filepath: str, magic_offset: int) -> None:
        async with CC(filepath) as cc:
            size_off = Crypt_MEarth.SIZE_OFFSETS[magic_offset]
            size = uint32(await cc.ext_read(size_off, 4), "little").value

            start_off = size_off + 4

            write_offs = Crypt_MEarth.WRITE_OFFSETS[magic_offset]

            chks = uint32(0, "little")
            cc.set_ptr(start_off)
            while await cc.read(stop_off=start_off + size):
                chks.value += sum(cc.chunk)
            w = chks.as_bytes
            for off in write_offs:
                await cc.ext_write(off, w)

    @staticmethod
    async def check_enc_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            magic_off = await Crypt_MEarth.get_magic_offset(filepath)
            if magic_off != -1:
                await Crypt_MEarth.encrypt_file(filepath, magic_off)

    @staticmethod
    async def get_magic_offset(filepath: str) -> int:
        async with aiofiles.open(filepath, "rb") as savegame:
            for off in Crypt_MEarth.MAGIC_OFFSETS:
                await savegame.seek(off)
                m = await savegame.read(len(Crypt_MEarth.MAGIC))
                if m == Crypt_MEarth.MAGIC:
                    return off
        return -1

