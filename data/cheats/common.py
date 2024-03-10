import discord
import asyncio
import aiofiles

class QuickCheatsError(Exception):
    """Exception raised for errors relating to quickcheats."""
    def __init__(self, message: str) -> None:
        self.message = message

class QuickCheats:
    @staticmethod
    async def findOffset_with_identifier32(savegame: aiofiles.threadpool.binary.AsyncFileIO, savegame_data: bytes | None, before_offset: bytes, after_offset: bytes | None, bytes_between: int) -> int:
        index = 0
        money_offset = -1
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
                    money_offset = identifier_offset + bytes_between
                    break

                index = identifier_offset + 1
            
            else:
                money_offset = identifier_offset + bytes_between
                break
        
        return money_offset

class TimeoutHelper:
    def __init__(self, embTimeout: discord.Embed) -> None:
        self.done = False
        self.embTimeout = embTimeout

    async def await_done(self) -> None:
        try:
            while not self.done:  # Continue waiting until done is True
                await asyncio.sleep(1)  # Sleep for 1 second to avoid busy-waiting
        except asyncio.CancelledError:
            pass  # Handle cancellation if needed
    
    async def handle_timeout(self, ctx: discord.ApplicationContext) -> None:
        if not self.done:
            await ctx.edit(embed=self.embTimeout, view=None)
            await asyncio.sleep(2)
            self.done = True
