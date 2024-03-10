import time
import aiofiles
import os
from .common import Converter, ConverterError
from data.crypto.rstar_crypt import Crypt_Rstar as crypt

class Converter_Rstar:
    @staticmethod
    def get_uint32(data: bytearray, seed: int) -> int:
        num1 = seed
        for index in range(len(data)):
            num2 = (num1 + int(data[index])) & 0xFF_FF_FF_FF
            num3 = (num2 + (num2 << 10)) & 0xFF_FF_FF_FF
            num1 = (num3 ^ num3 >> 6) & 0xFF_FF_FF_FF
        num4 = (num1 + (num1 << 3)) & 0xFF_FF_FF_FF
        num5 = (num4 ^ num4 >> 11) & 0xFF_FF_FF_FF
        return (num5 + (num5 << 15)) & 0xFF_FF_FF_FF
    
    @staticmethod
    async def handleTitle(filePath: str) -> None:
        unix = int(time.time())
        date = time.strftime("%d/%m/%y %H:%M:%S", time.gmtime(unix))
        TITLE = f"~b~HTOS CONVERTER ~p~∑ ~g~‹ - {date}".encode("utf-16le")
        NULL_BYTES = bytes([0] * (0x104 - 0x4))

        async with aiofiles.open(filePath, "r+b") as file:
            seed_bytes = bytearray(await file.read(4))
            seed_bytes = seed_bytes[::-1]
            seed = Converter_Rstar.get_uint32(seed_bytes, 0)

            await file.seek(0x4) # title start
            await file.write(NULL_BYTES)
            await file.seek(0x4)
            await file.write(TITLE)
            await file.seek(0x4)

            title_bytes = bytearray(await file.read(0x100))
            chks = format(Converter_Rstar.get_uint32(title_bytes, seed), "08x")
            chks_bytes = bytes.fromhex(chks)

            await file.seek(0x104)
            await file.write(chks_bytes)

    @staticmethod
    async def convertFile_GTAV(filePath: str) -> str | None:
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

        except (ValueError, IOError):
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
                await Converter_Rstar.handleTitle(filePath)

                await crypt.encryptFile(filePath, crypt.RDR2_PC_HEADER_OFFSET)
            
            elif header != crypt.RDR2_HEADER and platform == "ps4":
                await crypt.decryptFile(os.path.dirname(filePath), crypt.RDR2_PS_HEADER_OFFSET)

                await Converter.pushBytes(crypt.RDR2_PS_HEADER_OFFSET, crypt.RDR2_PC_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath)

                await crypt.encryptFile(filePath, crypt.RDR2_PC_HEADER_OFFSET)
            
            elif header == crypt.RDR2_HEADER and platform == "pc":
                await Converter.pushBytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath)
            
            elif header != crypt.RDR2_HEADER and platform == "pc":
                await crypt.decryptFile(os.path.dirname(filePath), crypt.RDR2_PC_HEADER_OFFSET)

                await Converter.pushBytes(crypt.RDR2_PC_HEADER_OFFSET, crypt.RDR2_PS_HEADER_OFFSET, filePath)
                await Converter_Rstar.handleTitle(filePath)
            
            else: raise ConverterError("File not supported!")

            if platform == "ps4": 
                return "CONVERTED: PS4 -> PC"
            else:
                return "CONVERTED: PC -> PS4"
        
        except (ValueError, IOError):
            raise ConverterError("File not supported!")
