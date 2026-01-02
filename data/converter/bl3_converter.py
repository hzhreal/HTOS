from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from utils.helpers import TimeoutHelper

import discord
from discord.ui.item import Item

from data.converter.exceptions import ConverterError
from data.crypto.bl3_crypt import Crypt_BL3 as crypt
from data.crypto.common import CustomCrypto
from data.crypto.exceptions import CryptoError
from utils.constants import OTHER_TIMEOUT, logger
from utils.embeds import embErrconv

class BL3_conv_button(discord.ui.View):
    """Discord button that is called when a decrypted BL3 save needs converting, gives user the choice of what platform to convert the save to."""
    def __init__(self, ctx: discord.ApplicationContext, helper: TimeoutHelper, filepath: str, ttwl: bool) -> None:
        self.ctx = ctx
        self.helper = helper
        self.filepath = filepath
        self.result = ""
        self.ttwl = ttwl
        super().__init__(timeout=OTHER_TIMEOUT)

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.helper.handle_timeout(self.ctx)
        self.result = "TIMED OUT"

    async def on_error(self, error: Exception, _: Item, __: discord.Interaction) -> None:
        self.disable_all_items()
        emb = embErrconv.copy()
        emb.description = emb.description.format(error=error)
        self.helper.embTimeout = emb
        await self.helper.handle_timeout(self.ctx)
        logger.info(f"{error} - {self.ctx.user.name}")
        self.result = "ERROR"

    @discord.ui.button(label="PS4 -> PC", style=discord.ButtonStyle.blurple, custom_id="BL3_PS4_TO_PC_CONV")
    async def ps4_to_pc_callback(self, _, interaction: discord.Interaction) -> None:
        platform = "ps4"
        await interaction.response.edit_message(view=None)
        try:
            await crypt.encrypt_file(self.filepath, "pc", self.ttwl)
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
            await crypt.encrypt_file(self.filepath, "ps4", self.ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("Invalid save!")

        self.helper.done = True
        self.result = Converter_BL3.obtain_ret_val(platform)

class Converter_BL3:
    @staticmethod
    async def convert_file(ctx: discord.ApplicationContext | None, helper: TimeoutHelper | None, filepath: str, ttwl: bool, emb_btn: discord.Embed | None) -> str:
        async with CustomCrypto(filepath) as cc:
            off = await cc.find(crypt.COMMON)
        if off != -1: 
            if not ctx or not helper or not emb_btn:
                return ""
            conv_button = BL3_conv_button(ctx, helper, filepath, ttwl)
            await ctx.edit(embed=emb_btn, view=conv_button)
            await helper.await_done()
            return conv_button.result
 
        # try decrypting it with ps4 keys
        try: 
            await crypt.decrypt_file(filepath, "ps4", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

        # read new data and check if its decrypted
        async with CustomCrypto(filepath) as cc:
            off = await cc.find(crypt.COMMON)
        # ps4 -> pc
        if off != -1: 
            platform = "ps4"
            try:
                await crypt.encrypt_file(filepath, "pc", ttwl)
            except CryptoError as e:
                raise ConverterError(e)
            except (ValueError, IOError, IndexError):
                raise ConverterError("File not supported!")
            return Converter_BL3.obtain_ret_val(platform)

        # not decrypted, rewrite to orignal data
        try: 
            await crypt.encrypt_file(filepath, "ps4", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

        # try decrypting with pc keys instead 
        try:
            await crypt.decrypt_file(filepath, "pc", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("File not supported!")

        # read new data and check if its decrypted
        async with CustomCrypto(filepath) as cc:
            off = await cc.find(crypt.COMMON)

        # pc -> ps4
        if off != -1: 
            platform = "pc"
            try:
                await crypt.encrypt_file(filepath, "ps4", ttwl)
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
