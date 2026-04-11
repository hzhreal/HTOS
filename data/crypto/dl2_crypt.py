import struct
import aiofiles

from data.crypto.common import CustomCrypto as CC

class Crypt_DL2:

    STRUCT_SIZE     = 20
    MAGIC_SGDS      = b"SGDS"
    MAGIC_SGDD      = b"SGDD"
    STRUCT_FMT      = "<IIQI"
    CRC_FIELD_OFF   = 8

    CRC64 = CC.anycrc.CRC(
        width=64,
        poly=0xAD93D23594C935A9,
        init=0xFF_FF_FF_FF_FF_FF_FF_FF,
        refin=True,
        refout=True,
        xorout=0xFF_FF_FF_FF_FF_FF_FF_FF,
    )

    @staticmethod
    async def _fix_crcs(filepath: str) -> None:
        async with CC(filepath, in_place=True) as cc:
            search_off = 0
            while True:
                off_s = await cc.find(Crypt_DL2.MAGIC_SGDS, search_off)
                off_d = await cc.find(Crypt_DL2.MAGIC_SGDD, search_off)

                candidates = [o for o in (off_s, off_d) if o >= 0]
                if not candidates:
                    break
                off = min(candidates)

                if off + Crypt_DL2.STRUCT_SIZE > cc.size:
                    break

                header = await cc.ext_read(off, Crypt_DL2.STRUCT_SIZE)
                _, seg_type, stored_crc, size = struct.unpack_from(Crypt_DL2.STRUCT_FMT, header)

                seg_start = off + Crypt_DL2.STRUCT_SIZE
                seg_end   = seg_start + size

                if seg_end > cc.size:
                    search_off = off + 4
                    continue

                if seg_type == 2 and size > 0:
                    calc_crc = None
                    pos = seg_start
                    while pos < seg_end:
                        n     = min(CC.CHUNKSIZE, seg_end - pos)
                        chunk = await cc.ext_read(pos, n)
                        calc_crc = Crypt_DL2.CRC64.calc(chunk, calc_crc)
                        pos += n

                    if calc_crc != stored_crc:
                        await cc.ext_write(off + Crypt_DL2.CRC_FIELD_OFF, struct.pack("<Q", calc_crc))

                search_off = off + 4

    @staticmethod
    async def decrypt_file(filepath: str) -> None:
        async with CC(filepath, in_place=False) as cc:
            gzip = cc.create_ctx_gzip_decompress()
            while await cc.read():
                await cc.decompress(gzip)

    @staticmethod
    async def encrypt_file(filepath: str) -> None:
        await Crypt_DL2._fix_crcs(filepath)
        async with CC(filepath, in_place=False) as cc:
            gzip = cc.create_ctx_gzip_compress()
            while await cc.read():
                await cc.compress(gzip)

    @staticmethod
    async def check_dec_ps(folderpath: str) -> None:
        files = await CC.obtain_files(folderpath)
        for filepath in files:
            async with aiofiles.open(filepath, "rb") as savegame:
                magic = await savegame.read(3)
            if magic == b"\x1F\x8B\x08":
                await Crypt_DL2.decrypt_file(filepath)

    @staticmethod
    async def check_enc_ps(filepath: str) -> None:
        async with aiofiles.open(filepath, "rb") as savegame:
            magic = await savegame.read(3)
        if magic != b"\x1F\x8B\x08":
            await Crypt_DL2.encrypt_file(filepath)

