import time
import aiofiles
from data.converter.common import Converter
from data.converter.exceptions import ConverterError
from data.crypto.common import CustomCrypto
from data.crypto.rstar_crypt import Crypt_Rstar as crypt
from utils.type_helpers import uint32

class Converter_Rstar:
    @staticmethod
    async def handle_title(cc: CustomCrypto, write_date_rdr2: bool = False, clear_rdr2_pc_chks: bool = False) -> None:
        unix = int(time.time())
        date = time.strftime("%d/%m/%y %H:%M:%S", time.gmtime(unix))
        if write_date_rdr2 or clear_rdr2_pc_chks:
            TITLE = f"@!HTOS CONVERTER!@ - {date}".encode("utf-16le") # buffersize 0x100
        else:
            TITLE = f"~b~HTOS CONVERTER ~p~∑ ~g~‹ - {date}".encode("utf-16le") # buffersize 0x100
        NULL_BYTES = bytes([0] * (0x104 - 0x4))

        await cc.w_stream.seek(0x4) # title start
        await cc.w_stream.write(NULL_BYTES)
        await cc.w_stream.seek(0x4)
        await cc.w_stream.write(TITLE)

        if write_date_rdr2:
            await cc.w_stream.seek(0x104)
            datesum = uint32(unix, "big")
            await cc.w_stream.write(datesum.as_bytes)

        if clear_rdr2_pc_chks:
            await cc.w_stream.seek(0x10C)
            await cc.w_stream.write(b"\x00" * 4)

    @staticmethod
    async def convert_file_GTAV(filepath: str) -> str:
        try:
            async with aiofiles.open(filepath, "rb") as file:
                await file.seek(crypt.GTAV_PC_HEADER_OFFSET)
                check_bytes = await file.read(len(crypt.GTAV_HEADER))
                if check_bytes == b"\x00\x00\x00\x00": # ps4 if true
                    platform = "ps4"
                    await file.seek(crypt.GTAV_PS_HEADER_OFFSET)
                    header = await file.read(len(crypt.GTAV_HEADER))
                else: # pc if true or invalid
                    platform = "pc"
                    header = await file.read(len(crypt.GTAV_HEADER))

            if header == crypt.GTAV_HEADER and platform == "ps4":
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.GTAV_PS_HEADER_OFFSET, crypt.GTAV_PC_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv)
                await crypt.encrypt_file(filepath, crypt.GTAV_PC_HEADER_OFFSET)

            elif header != crypt.GTAV_HEADER and platform == "ps4":
                await crypt.decrypt_file(filepath, crypt.GTAV_PS_HEADER_OFFSET)
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.GTAV_PS_HEADER_OFFSET, crypt.GTAV_PC_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv)
                await crypt.encrypt_file(filepath, crypt.GTAV_PC_HEADER_OFFSET)

            elif header == crypt.GTAV_HEADER and platform == "pc":
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.GTAV_PC_HEADER_OFFSET, crypt.GTAV_PS_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv)

            elif header != crypt.GTAV_HEADER and platform == "pc":
                await crypt.decrypt_file(filepath, crypt.GTAV_PC_HEADER_OFFSET)
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.GTAV_PC_HEADER_OFFSET, crypt.GTAV_PS_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv)

            else:
                raise ConverterError("File not supported!")

            if platform == "ps4": 
                return "CONVERTED: PS4 -> PC"
            else:
                return "CONVERTED: PC -> PS4"
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

    @staticmethod
    async def convert_file_RDR2(filepath: str) -> None:
        try:
            async with aiofiles.open(filepath, "rb") as file:
                await file.seek(crypt.RDR2_PC_HEADER_OFFSET)
                check_bytes = await file.read(len(crypt.RDR2_HEADER))
                if check_bytes == b"\x00\x00\x00\x00": # ps4 if true
                    platform = "ps4"
                    await file.seek(crypt.RDR2_PS_HEADER_OFFSET)
                    header = await file.read(len(crypt.RDR2_HEADER))
                else: # pc if true or invalid
                    platform = "pc"
                    header = await file.read(len(crypt.RDR2_HEADER))

            if header == crypt.RDR2_HEADER and platform == "ps4":
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.RDR2_PS_HEADER_OFFSET, crypt.RDR2_PC_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv, write_date_rdr2=True)
                await crypt.encrypt_file(filepath, crypt.RDR2_PC_HEADER_OFFSET)

            elif header != crypt.RDR2_HEADER and platform == "ps4":
                await crypt.decrypt_file(filepath, crypt.RDR2_PS_HEADER_OFFSET)
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.RDR2_PS_HEADER_OFFSET, crypt.RDR2_PC_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv, write_date_rdr2=True)
                await crypt.encrypt_file(filepath, crypt.RDR2_PC_HEADER_OFFSET)

            elif header == crypt.RDR2_HEADER and platform == "pc":
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv, clear_rdr2_pc_chks=True)

            elif header != crypt.RDR2_HEADER and platform == "pc":
                await crypt.decrypt_file(filepath, crypt.RDR2_PC_HEADER_OFFSET)
                async with Converter(filepath, False) as cv:
                    await cv.push_bytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET)
                    await Converter_Rstar.handle_title(cv, clear_rdr2_pc_chks=True)

            else:
                raise ConverterError("File not supported!")

            if platform == "ps4":
                return "CONVERTED: PS4 -> PC"
            else:
                return "CONVERTED: PC -> PS4"
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")
