import aiofiles

class QuickCheatsError(Exception):
    """Exception raised for errors relating to quickcheats."""
    def __init__(self, message: str) -> None:
        self.message = message

class QuickCheats:
    @staticmethod
    async def findOffset_with_identifier32(savegame: aiofiles.threadpool.binary.AsyncFileIO, savegame_data: bytes | None, before_offset: bytes, after_offset: bytes | None, bytes_between: int) -> int:
        """Used to find an offset using values that identify the location (32 bit / 4 byte)."""
        index = 0
        target_offset = -1
        if savegame_data is None:
            savegame_data = await savegame.read()

        while index < len(savegame_data):
            identifier_offset = savegame_data.find(before_offset, index)
            if identifier_offset == -1: 
                break
            
            if after_offset is not None:
                second_identifier_offset = identifier_offset + bytes_between + 4
                await savegame.seek(second_identifier_offset)
                second_identifier_data = await savegame.read(4)

                if second_identifier_data == after_offset:
                    target_offset = identifier_offset + bytes_between
                    break

                index = identifier_offset + 1
            
            else:
                target_offset = identifier_offset + bytes_between
                break
        
        return target_offset