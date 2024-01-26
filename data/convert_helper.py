import aiofiles
from .crypto_functions import CustomCrypto
import os
import time

class ConverterError(Exception):
    """Exception raised for errors relating to the converter."""
    def __init__(self, message: str) -> None:
        self.message = message

class Converter:
    # When converting we have to move PSIN or RSAV header to the start bytes
    # GTA V: 
        # PS4 is 0x114
        # PC is 0x108
    # RDR 2:
        # PS4 is 0x120
        # PC is 0x110
    @staticmethod
    async def pushBytes(src_offset: int, dest_offset: int, filePath: str) -> None:
        async with aiofiles.open(filePath, "rb") as file:
            await file.seek(0)
            data = await file.read()
            data += b"\x00" * max(src_offset - dest_offset, 0)

            await file.seek(src_offset)
            data_to_move = await file.read()

            new_data = data[:src_offset]
            
        async with aiofiles.open(filePath, "wb") as file:
            await file.seek(0)
            await file.write(new_data)
            
            await file.seek(dest_offset)
            await file.write(data_to_move)

    class Rstar:


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
            SEED = 10338022

            async with aiofiles.open(filePath, "r+b") as file:
                await file.write(b"\x00\x00\x00\x01")
                await file.seek(0x4) # title start
                await file.write(NULL_BYTES)
                await file.seek(0x4)
                await file.write(TITLE)
                await file.seek(0x4)

                title_bytes = bytearray(await file.read(0x100))
                chks = format(Converter.Rstar.get_uint32(title_bytes, SEED), "08x")
                print(chks)
                chks_bytes = bytes.fromhex(chks)

                await file.seek(0x104)
                await file.write(chks_bytes)

        @staticmethod
        async def convertFile_GTAV(filePath: str) -> str | None:
            PS_HEADER_OFFSET = 0x114
            PC_HEADER_OFFSET = 0x108
            HEADER = b"PSIN"

            try:
                async with aiofiles.open(filePath, "rb") as file:
                    await file.seek(PC_HEADER_OFFSET)
                    check_bytes = await file.read(4)
                
                    if check_bytes == b"\x00\x00\x00\x00": # ps4 if true
                        platform = "ps4"
                        await file.seek(PS_HEADER_OFFSET)
                        header = await file.read(4)
                    
                    else: # pc if true or invalid 
                        platform = "pc"
                        header = await file.read(4)
            
                    if header == HEADER and platform == "ps4":
                        print("decrypted ps4 file recognized")
                        await Converter.pushBytes(PS_HEADER_OFFSET, PC_HEADER_OFFSET, filePath)
                        await Converter.Rstar.handleTitle(filePath)

                        await CustomCrypto.Rstar.encryptFile(filePath, PC_HEADER_OFFSET)
                    
                    elif header != HEADER and platform == "ps4":
                        print("encrypted ps4 file recognized")
                        await CustomCrypto.Rstar.decryptFile(os.path.dirname(filePath), PS_HEADER_OFFSET)

                        await Converter.pushBytes(PS_HEADER_OFFSET, PC_HEADER_OFFSET, filePath)
                        await Converter.Rstar.handleTitle(filePath)

                        await CustomCrypto.Rstar.encryptFile(filePath, PC_HEADER_OFFSET)

                    elif header == HEADER and platform == "pc":
                        print("decrypted pc file recognized")
                        await Converter.pushBytes(PC_HEADER_OFFSET, PS_HEADER_OFFSET, filePath)
                        await Converter.Rstar.handleTitle(filePath)

                    elif header != HEADER and platform == "pc":
                        print("encrypted pc file recognized")
                        await CustomCrypto.Rstar.decryptFile(os.path.dirname(filePath), PC_HEADER_OFFSET)

                        await Converter.pushBytes(PC_HEADER_OFFSET, PS_HEADER_OFFSET, filePath)
                        await Converter.Rstar.handleTitle(filePath)
                    
                    else: raise ConverterError("File not supported!")

                    if platform == "ps4": return "CONVERTED: PS4 -> PC"
                    else: return "CONVERTED: PC -> PS4"

            except (ValueError, IOError):
                raise ConverterError("File not supported!")
        
        @staticmethod
        async def convertFile_RDR2(filePath: str) -> None:
            PS_HEADER_OFFSET = 0x120
            PC_HEADER_OFFSET = 0x110
            HEADER = b"RSAV"

            try:
                async with aiofiles.open(filePath, "rb") as file:
                    await file.seek(PC_HEADER_OFFSET)
                    check_bytes = await file.read(4)

                    if check_bytes == b"\x00\x00\x00\x00": # ps4 if true
                        platform = "ps4"
                        await file.seek(PS_HEADER_OFFSET)
                        header = await file.read(4)
                    
                    else: # pc if true or invalid
                        platform = "pc"
                        header = await file.read(4)
                
                if header == HEADER and platform == "ps4":
                    print("decrypted ps4 file recognized")
                    await Converter.pushBytes(PS_HEADER_OFFSET, PC_HEADER_OFFSET, filePath)
                    await Converter.Rstar.handleTitle(filePath)

                    await CustomCrypto.Rstar.encryptFile(filePath, PC_HEADER_OFFSET)
                
                elif header != HEADER and platform == "ps4":
                    print("encrypted ps4 file recognized")
                    await CustomCrypto.Rstar.decryptFile(os.path.dirname(filePath), PS_HEADER_OFFSET)

                    await Converter.pushBytes(PS_HEADER_OFFSET, PC_HEADER_OFFSET, filePath)
                    await Converter.Rstar.handleTitle(filePath)

                    await CustomCrypto.Rstar.encryptFile(filePath, PC_HEADER_OFFSET)
                
                elif header == HEADER and platform == "pc":
                    print("decrypted pc file recognized")
                    await Converter.pushBytes(PC_HEADER_OFFSET, PS_HEADER_OFFSET, filePath)
                    await Converter.Rstar.handleTitle(filePath)
                
                elif header != HEADER and platform == "pc":
                    print("encrypted pc file recognized")
                    await CustomCrypto.Rstar.decryptFile(os.path.dirname(filePath), PC_HEADER_OFFSET)

                    await Converter.pushBytes(PC_HEADER_OFFSET, PS_HEADER_OFFSET, filePath)
                    await Converter.Rstar.handleTitle(filePath)
                
                else: raise ConverterError("File not supported!")

                if platform == "ps4": return "CONVERTED: PS4 -> PC"
                else: return "CONVERTED: PC -> PS4"
            
            except (ValueError, IOError):
                raise ConverterError("File not supported!")