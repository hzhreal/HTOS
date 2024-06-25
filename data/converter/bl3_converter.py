import aiofiles
import os
import discord
from discord.ui.item import Item
from data.converter.common import ConverterError
from data.crypto import Crypt_BL3 as crypt
from data.crypto.common import CryptoError
from utils.helpers import TimeoutHelper
from utils.constants import OTHER_TIMEOUT, emb_conv_choice, logger, Color, Embed_t

class BL3_conv_button(discord.ui.View):
    """Discord button that is called when a decrypted BL3 save needs converting, gives user the choice of what platform to convert the save to."""
    def __init__(self, ctx: discord.ApplicationContext, helper: TimeoutHelper, filePath: str, ttwl: bool) -> None:
        self.ctx = ctx
        self.helper = helper
        self.filePath = filePath
        self.result = ""
        self.ttwl = ttwl
        super().__init__(timeout=OTHER_TIMEOUT)
                
    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.helper.handle_timeout(self.ctx)
        self.result = "TIMED OUT"

    async def on_error(self, error: Exception, _: Item, __: discord.Interaction) -> None:
        self.disable_all_items()
        embedErrb = discord.Embed(title=f"ERROR!", description=f"Could not convert: {error}.", colour=Color.DEFAULT.value)
        embedErrb.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        self.helper.embTimeout = embedErrb
        await self.helper.handle_timeout(self.ctx)
        logger.error(f"{error} - {self.ctx.user.name}")
        self.result = "ERROR"
            
    @discord.ui.button(label="PS4 -> PC", style=discord.ButtonStyle.blurple, custom_id="BL3_PS4_TO_PC_CONV")
    async def ps4_to_pc_callback(self, _, interaction: discord.Interaction) -> None:
        platform = "ps4"
        await interaction.response.edit_message(view=None)
        try:
            await crypt.encryptFile(self.filePath, "pc", self.ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("Invalid save!")
        
        self.helper.done = True
        self.result = Converter_BL3.obtain_ret_val(platform)
        
    @discord.ui.button(label="PC -> PS4", style=discord.ButtonStyle.blurple, custom_id="BL3_PC_TO_PS4_CONV")
    async def pc_to_ps4_callback(self, _, interaction: discord.Interaction) -> None:
        platform = "pc"
        await interaction.response.edit_message(view=None)
        try:
            await crypt.encryptFile(self.filePath, "ps4", self.ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("Invalid save!")
        
        self.helper.done = True
        self.result = Converter_BL3.obtain_ret_val(platform)

class Converter_BL3:
    @staticmethod
    async def convertFile(ctx: discord.ApplicationContext, helper: TimeoutHelper, filePath: str, ttwl: bool) -> str:
        async with aiofiles.open(filePath, "rb") as savegame:
            original_saveData = await savegame.read()
        
        if crypt.searchData(original_saveData, crypt.COMMON):
            conv_button = BL3_conv_button(ctx, helper, filePath, ttwl)
            await ctx.edit(embed=emb_conv_choice, view=conv_button)
            await helper.await_done()
            return conv_button.result
        
        # try decrypting it with ps4 keys
        try: 
            await crypt.decryptFile(os.path.dirname(filePath), "ps4", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

        # read new data and check if its decrypted
        async with aiofiles.open(filePath, "rb") as savegame:
            saveData = await savegame.read()

        # ps4 -> pc
        if crypt.searchData(saveData, crypt.COMMON):
            platform = "ps4"
            try:
                await crypt.encryptFile(filePath, "pc", ttwl)
            except CryptoError as e:
                raise ConverterError(e)
            except (ValueError, IOError, IndexError):
                raise ConverterError("File not supported!")
            return Converter_BL3.obtain_ret_val(platform)
        
        # not decrypted, rewrite to orignal data
        async with aiofiles.open(filePath, "wb") as savegame:
            await savegame.write(original_saveData)
        
        # try decrypting with pc keys instead 
        try:
            await crypt.decryptFile(os.path.dirname(filePath), "pc", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

        # read new data and check if its decrypted
        async with aiofiles.open(filePath, "rb") as savegame:
            saveData = await savegame.read()

        # pc -> ps4
        if crypt.searchData(saveData, crypt.COMMON):
            platform = "pc"
            try:
                await crypt.encryptFile(filePath, "ps4", ttwl)
            except CryptoError as e:
                raise ConverterError(e)
            except (ValueError, IOError, IndexError):
                raise ConverterError("File not supported!")
            return Converter_BL3.obtain_ret_val(platform)
        else:
            raise ConverterError("File not supported!") # invalid save
    
    @staticmethod
    def obtain_ret_val(platform: str) -> str:
        if platform == "ps4": 
            return "CONVERTED: PS4 -> PC"
        else: 
            return "CONVERTED: PC -> PS4"
