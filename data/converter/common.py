import aiofiles

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
