import aiofiles
from data.converter.exceptions import ConverterError
from data.crypto.common import CustomCrypto
from data.crypto.xeno2_crypt import Crypt_Xeno2 as crypt
from data.crypto.exceptions import CryptoError

class Converter_Xeno2:
    PS4_SIZE = 0x12A200
    PC_SIZE = 0x12A1F8
    MARKER_START = 0x08
    MD5_HEADER_SIZE = 0x20
    HCD_START_PS4 = 0x07BCA0 + MD5_HEADER_SIZE
    HCD_START_PC = 0x07BCB8
    MARKER = bytes([
        0x58, 0x56, 0x32, 0x53, 0x41, 0x54, 0xD6, 0x31
    ])

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
            await self.r_stream.seek(Converter_Xeno2.MARKER_START)
            marker = await self.r_stream.read(len(Converter_Xeno2.MARKER))
            return marker == Converter_Xeno2.MARKER

        async def pack_data(self) -> None:
            assert not self.in_place

            if self.size != Converter_Xeno2.PS4_SIZE:
                raise ConverterError("Unsupported save!")

            await self.r_stream.seek(0)
            md5_header = await self.r_stream.read(Converter_Xeno2.MD5_HEADER_SIZE)
            sav_header = await self.r_stream.read(crypt.SAVE_HEADER_SIZE)

            # write first_8
            first_8 = await self.r_stream.read(Converter_Xeno2.MARKER_START)
            await self.w_stream.write(first_8)

            # write marker
            await self.w_stream.write(Converter_Xeno2.MARKER)

            # write middle section
            self.set_ptr(await self.r_stream.tell())
            while await self.read(stop_off=Converter_Xeno2.HCD_START_PS4):
                await self.w_stream.write(self.chunk)

            # write hcd section
            cur = await self.w_stream.seek(Converter_Xeno2.HCD_START_PC)
            stop_off = self.chunk_end + Converter_Xeno2.PC_SIZE - (cur + crypt.SAVE_HEADER_SIZE + Converter_Xeno2.MD5_HEADER_SIZE)
            while await self.read(stop_off=stop_off):
                await self.w_stream.write(self.chunk)

            # write headers
            await self.w_stream.write(sav_header)
            await self.w_stream.write(md5_header)

            assert await self.w_stream.tell() == Converter_Xeno2.PC_SIZE

        async def unpack_data(self) -> None:
            assert not self.in_place

            if self.size != Converter_Xeno2.PC_SIZE:
                raise CryptoError("Unsupported save!")

            # write headers
            hcd_end = await self.r_stream.seek(self.size - Converter_Xeno2.MD5_HEADER_SIZE - crypt.SAVE_HEADER_SIZE)
            sav_header = await self.r_stream.read(crypt.SAVE_HEADER_SIZE)
            md5_header = await self.r_stream.read(Converter_Xeno2.MD5_HEADER_SIZE)
            await self.w_stream.write(md5_header)
            await self.w_stream.write(sav_header)

            # write first_8
            await self.r_stream.seek(0)
            first_8 = await self.r_stream.read(Converter_Xeno2.MARKER_START)
            await self.w_stream.write(first_8)

            # write middle section
            self.set_ptr(Converter_Xeno2.MARKER_START + len(Converter_Xeno2.MARKER))
            while await self.read(stop_off=Converter_Xeno2.HCD_START_PC):
                await self.w_stream.write(self.chunk)

            # write hcd_section
            await self.w_stream.seek(Converter_Xeno2.HCD_START_PS4)
            while await self.read(stop_off=hcd_end):
                await self.w_stream.write(self.chunk)

            # pad at the end
            pad = Converter_Xeno2.PS4_SIZE - await self.w_stream.tell()
            await self.w_stream.write(bytes(pad))

            assert await self.w_stream.tell() == Converter_Xeno2.PS4_SIZE

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
                    raise ConverterError("Unsupported save!")
        except (ValueError, IOError, IndexError, CryptoError):
            raise ConverterError("File not supported!")
        return ret
