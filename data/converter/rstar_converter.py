import time
import aiofiles
import os
from data.converter.common import Converter, ConverterError
from data.crypto.rstar_crypt import Crypt_Rstar as crypt
from utils.type_helpers import uint32

class Converter_Rstar: 
    @staticmethod
    async def handleTitle(filePath: str, write_date_rdr2: bool = False, clear_rdr2_pc_chks: bool = False) -> None:
        unix = int(time.time())
        date = time.strftime("%d/%m/%y %H:%M:%S", time.gmtime(unix))
        if write_date_rdr2 or clear_rdr2_pc_chks:
            TITLE = f"@!HTOS CONVERTER!@ - {date}".encode("utf-16le") # buffersize 0x100
        else:
            TITLE = f"~b~HTOS CONVERTER ~p~∑ ~g~‹ - {date}".encode("utf-16le") # buffersize 0x100
        NULL_BYTES = bytes([0] * (0x104 - 0x4))

        async with aiofiles.open(filePath, "r+b") as file:
            await file.seek(0x4) # title start
            await file.write(NULL_BYTES)
            await file.seek(0x4)
            await file.write(TITLE)

            if write_date_rdr2:
                await file.seek(0x104)
                datesum = uint32(unix, "big")
                await file.write(datesum.as_bytes)

            if clear_rdr2_pc_chks:
                await file.seek(0x10C)
                await file.write(b"\x00" * 4)

    @staticmethod
    async def convertFile_GTAV(filePath: str) -> str:
        try:
            async with aiofiles.open(filePath, "rb") as file:
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
                    await Converter.pushBytes(crypt.GTAV_PS_HEADER_OFFSET, crypt.GTAV_PC_HEADER_OFFSET, filePath)
                    await Converter_Rstar.handleTitle(filePath)

                    await crypt.encryptFile(filePath, crypt.GTAV_PC_HEADER_OFFSET)
                
                elif header != crypt.GTAV_HEADER and platform == "ps4":
                    await crypt.decryptFile(os.path.dirname(filePath), crypt.GTAV_PS_HEADER_OFFSET)

                    await Converter.pushBytes(crypt.GTAV_PS_HEADER_OFFSET, crypt.GTAV_PC_HEADER_OFFSET, filePath)
                    await Converter_Rstar.handleTitle(filePath)

                    await crypt.encryptFile(filePath, crypt.GTAV_PC_HEADER_OFFSET)

                elif header == crypt.GTAV_HEADER and platform == "pc":
                    await Converter.pushBytes(crypt.GTAV_PC_HEADER_OFFSET, crypt.GTAV_PS_HEADER_OFFSET, filePath)
                    await Converter_Rstar.handleTitle(filePath)

                elif header != crypt.GTAV_HEADER and platform == "pc":
                    await crypt.decryptFile(os.path.dirname(filePath), crypt.GTAV_PC_HEADER_OFFSET)

                    await Converter.pushBytes(crypt.GTAV_PC_HEADER_OFFSET, crypt.GTAV_PS_HEADER_OFFSET, filePath)
                    await Converter_Rstar.handleTitle(filePath)
                
                else: raise ConverterError("File not supported!")

                if platform == "ps4": 
                    return "CONVERTED: PS4 -> PC"
                else: 
                    return "CONVERTED: PC -> PS4"

        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")
    
    @staticmethod
    async def convertFile_RDR2(filePath: str) -> None:
        try:
            async with aiofiles.open(filePath, "rb") as file:
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
                await Converter.pushBytes(crypt.RDR2_PS_HEADER_OFFSET, crypt.RDR2_PC_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath, write_date_rdr2=True)

                await crypt.encryptFile(filePath, crypt.RDR2_PC_HEADER_OFFSET)
            
            elif header != crypt.RDR2_HEADER and platform == "ps4":
                await crypt.decryptFile(os.path.dirname(filePath), crypt.RDR2_PS_HEADER_OFFSET)

                await Converter.pushBytes(crypt.RDR2_PS_HEADER_OFFSET, crypt.RDR2_PC_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath, write_date_rdr2=True)

                await crypt.encryptFile(filePath, crypt.RDR2_PC_HEADER_OFFSET)
            
            elif header == crypt.RDR2_HEADER and platform == "pc":
                await Converter.pushBytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath, clear_rdr2_pc_chks=True)
            
            elif header != crypt.RDR2_HEADER and platform == "pc":
                await crypt.decryptFile(os.path.dirname(filePath), crypt.RDR2_PC_HEADER_OFFSET)

                await Converter.pushBytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath, clear_rdr2_pc_chks=True)
            
            else: raise ConverterError("File not supported!")

            if platform == "ps4": 
                return "CONVERTED: PS4 -> PC"
            else:
                return "CONVERTED: PC -> PS4"
        
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")
