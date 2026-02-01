import aiofiles
from data.converter.exceptions import ConverterError
from data.crypto.common import CustomCrypto
from data.crypto.xeno2_crypt import Crypt_Xeno2 as crypt
from utils.type_helpers import uint32

class Converter_Xeno2:
    FALLBACK_HEADER = bytes([
        0x23, 0x53, 0x41, 0x56, 0x00, 0xED, 0xF6, 0x99, 0xC2, 0xDC, 0x2F, 0x81, 0xE4, 0x23, 0xD8, 0xD5,
        0x74, 0x5D, 0x0E, 0x8C, 0x87, 0xFC, 0xB6, 0x68, 0xB5, 0x0F, 0x04, 0xB8, 0x34, 0xA0, 0x76, 0xF0,
        0x16, 0xF5, 0x18, 0xA5, 0x1B, 0xCC, 0xDF, 0x6C, 0x6D, 0xE4, 0x39, 0x82, 0xA1, 0x12, 0xBA, 0xA2,
        0xE0, 0x36, 0xBA, 0xAE, 0x60, 0x00, 0x7F, 0x50, 0x03, 0xA4, 0xA7, 0xE6, 0x74, 0x1A, 0xFD, 0x98,
        0xF4, 0x9F, 0x5A, 0x22, 0x91, 0xBE, 0x17, 0xBC, 0xBC, 0x28, 0xD1, 0x37, 0xB3, 0xAA, 0x7B, 0x1C,
        0x5D, 0x5B, 0x03, 0xCE, 0x80, 0x7F, 0x7D, 0x29, 0xC2, 0xDD, 0xBE, 0x12, 0x07, 0x39, 0xE8, 0xFA,
        0x07, 0x75, 0x8C, 0x0B, 0xA0, 0xA9, 0xBF, 0xFC, 0x68, 0xF6, 0x3F, 0x38, 0x96, 0xC2, 0x86, 0x79,
        0x27, 0x6F, 0x43, 0x83, 0x98, 0xB5, 0xC3, 0x4A, 0xBA, 0xDB, 0xBC, 0x66, 0x60, 0xA1, 0x12, 0x00,
    ])
    assert len(FALLBACK_HEADER) == crypt.SAVE_HEADER_SIZE
    MARKER = bytes([
        0x47, 0xFE, 0xDF, 0x4C, 0x55, 0x54, 0xD6, 0x20
    ])
    ID_OFFSET = 0x08
    PAD_SIZE = 16
    SAVE_MAGIC_HEADER = b"H\x89\x01L"

    class Xeno2(CustomCrypto):
        def __init__(self, filepath: str) -> None:
            super().__init__(filepath, in_place=False)

        async def has_dual_magic(self) -> bool:
            await self.r_stream.seek(0x20)
            dword = await self.r_stream.read(4)
            if dword != crypt.DEC_MAGIC:
                return False

            await self.r_stream.seek(0x20 + 0x80)
            dword = await self.r_stream.read(4)
            return dword == crypt.DEC_MAGIC

        async def has_marker(self) -> bool:
            await self.r_stream.seek(Converter_Xeno2.ID_OFFSET)
            marker = await self.r_stream.read(len(Converter_Xeno2.MARKER))
            return marker == Converter_Xeno2.MARKER

        async def pack_data(self) -> None:
            assert not self.in_place

            # dont include first 0x20 bytes
            await self.r_stream.seek(0x20)
            # read header
            header = await self.r_stream.read(crypt.SAVE_HEADER_SIZE)

            # write id part
            id_part = await self.r_stream.read(Converter_Xeno2.ID_OFFSET)
            await self.w_stream.write(id_part)
            # write marker
            await self.w_stream.write(Converter_Xeno2.MARKER)

            # copy the rest of the data
            self.set_ptr(await self.r_stream.tell())
            while await self.read():
                await self.w_stream.write(self.chunk)

            # write header and padding at the end
            await self.w_stream.write(header)
            pad = bytes([0] * Converter_Xeno2.PAD_SIZE)
            await self.w_stream.write(pad)

        async def unpack_data(self) -> None:
            assert not self.in_place

            header_off = self.size - crypt.SAVE_HEADER_SIZE - Converter_Xeno2.PAD_SIZE
            if header_off < 0:
                raise ConverterError("Unsupported save!")
            await self.r_stream.seek(header_off)
            header = await self.r_stream.read(crypt.SAVE_HEADER_SIZE)
            await self.w_stream.write(header)

            # write id part
            await self.r_stream.seek(0)
            id_part = await self.r_stream.read(Converter_Xeno2.ID_OFFSET)
            await self.w_stream.write(id_part)

            # skip 8 bytes ahead
            self.set_ptr(Converter_Xeno2.ID_OFFSET + 8)
            # copy the rest
            while await self.read(stop_off=header_off):
                await self.w_stream.write(self.chunk)

        async def unpack_fallback(self) -> None:
            # write fallback header
            await self.w_stream.write(Converter_Xeno2.FALLBACK_HEADER)

            # write id_part
            await self.r_stream.seek(0)
            id_part = await self.r_stream.read(Converter_Xeno2.ID_OFFSET)
            await self.w_stream.write(id_part)

            # skip 8 bytes ahead
            self.set_ptr(Converter_Xeno2.ID_OFFSET + 8)
            # copy the rest
            stop_off = self.size - crypt.SAVE_HEADER_SIZE - Converter_Xeno2.PAD_SIZE
            while await self.read(stop_off=stop_off):
                await self.w_stream.write(self.chunk)

    @staticmethod
    async def convert_file(filepath: str) -> str:
        try:
            # decrypt PS4 file if it is not already decrypted
            async with aiofiles.open(filepath, "rb") as savegame:
                magic = await savegame.read(len(crypt.DEC_MAGIC))
            # if the header is present then it is a PC file
            if magic != crypt.DEC_MAGIC:
                # not a PC file, check if it is encrypted
                await crypt.check_dec_ps(filepath)

            async with Converter_Xeno2.Xeno2(filepath) as cc:
                if await cc.has_dual_magic():
                    ret = "CONVERTED: PS4 -> PC"
                    await cc.pack_data()
                elif await cc.has_marker():
                    ret = "CONVERTED PC -> PS4"
                    await cc.unpack_data()
                else:
                    ret = "CONVERTED PC -> PS4 (FALLBACK)"
                    await cc.unpack_fallback()

            if ret != "CONVERTED: PS4 -> PC":
                # we need to generate the initial header
                async with CustomCrypto(filepath, in_place=False) as cc:
                    await cc.w_stream.write(Converter_Xeno2.SAVE_MAGIC_HEADER)
                    full_size = uint32(cc.size + 0x20, "little")
                    await cc.w_stream.write(full_size.as_bytes)
                    size = uint32(cc.size, "little")
                    await cc.w_stream.write(size.as_bytes)
                    await cc.w_stream.write(b"\x00\x00\x00\x00")
                    await cc.w_stream.write(bytes([0] * 16)) # space for md5 hash

                    # write the rest
                    while await cc.read():
                        await cc.w_stream.write(cc.chunk)

        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")
        return ret
