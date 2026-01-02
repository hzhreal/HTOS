from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from utils.helpers import TimeoutHelper

import discord
import asyncio
import aiofiles

from discord.ui.item import Item
from typing import Literal

from data.crypto.rstar_crypt import Crypt_Rstar as crypt
from data.cheats.common import QuickCheats
from data.cheats.exceptions import QuickCheatsError
from utils.constants import OTHER_TIMEOUT, logger
from utils.embeds import embDone_G, embchErr, embchgtav
from utils.type_helpers import uint32

class Cheats_GTAV:
    MONEY_LIMIT = 0x7FFFFFFF
    CHARACTERS = ["FRANKLIN", "MICHAEL", "TREVOR"]
    MONEY_OFFSET_IDENTIFIER_BEFORE = {
        "Franklin": b"\x44\xBD\x69\x82",
        "Michael": b"\x03\x24\xC3\x1D",
        "Trevor": b"\x8D\x75\x04\x7D"
    }
    BYTES_BETWEEN_IDENTIFIER = 4

    class MoneyModal(discord.ui.Modal):
        """Modal to modify money value for GTA V."""
        def __init__(self, ctx: discord.ApplicationContext, helper: TimeoutHelper, filepath: str, platform: Literal["ps4", "pc"]) -> None:
            super().__init__(title="Alter money", timeout=None)
            self.ctx = ctx
            self.helper = helper
            self.filepath = filepath
            self.platform = platform
            self.add_item(discord.ui.InputText(
                label="Choose character",
                custom_id="SelectCharacterMoney_GTAV",
                placeholder="Franklin | Michael | Trevor",
                max_length=8,
                style=discord.InputTextStyle.short
            ))
            self.add_item(discord.ui.InputText(
                label="Choose value",
                custom_id="ValueChooseMoney_GTAV",
                placeholder="99999",
                max_length=10,
                style=discord.InputTextStyle.short,
            ))

        async def on_error(self, err: Exception, _: discord.Interaction) -> None:
            if isinstance(err, QuickCheatsError):
                await self.ctx.respond(err, ephemeral=True)
            else:
                logger.info(f"Error with modal: {err}")

        async def callback(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            await asyncio.sleep(2)
            if not self.helper.done:
                character = self.children[0].value
                money = self.children[1].value
                if character.upper() not in Cheats_GTAV.CHARACTERS or not money.isdigit():
                    self.stop()
                    raise QuickCheatsError("Invalid input!")
                else:
                    character = list(character.lower())
                    character[0] = character[0].upper()
                    character = "".join(character)
                    money = int(money)
                    await Cheats_GTAV.change_money(self.filepath, money, character, self.platform)
                    stats = await Cheats_GTAV.fetch_stats(self.filepath, self.platform)
                    embLoaded = Cheats_GTAV.loaded_embed(stats)
                    await self.ctx.edit(embed=embLoaded)

    class CheatsButton(discord.ui.View):
        """Button used for GTA V cheats."""
        def __init__(self, ctx: discord.ApplicationContext, helper: TimeoutHelper, filepath: str, platform: Literal["ps4", "pc"]) -> None:
            super().__init__(timeout=OTHER_TIMEOUT)
            self.ctx = ctx
            self.helper = helper
            self.filepath = filepath
            self.platform = platform

        async def on_timeout(self) -> None:
            if not self.helper.done:
                self.disable_all_items()
                if self.platform == "pc":
                    await crypt.encrypt_file(self.filepath, crypt.GTAV_PC_HEADER_OFFSET)
                await self.helper.handle_timeout(self.ctx)

        async def on_error(self, error: Exception, _: Item, __: discord.Interaction) -> None:
            self.disable_all_items()
            emb = embchErr.copy()
            emb.description = emb.description.format(error=error)
            self.helper.embTimeout = emb
            await self.helper.handle_timeout(self.ctx)
            logger.info(f"{error} - {self.ctx.user.name}")

        @discord.ui.button(label="Change money", style=discord.ButtonStyle.primary, custom_id="ChangeMoney_GTAV")
        async def change_money_callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(Cheats_GTAV.MoneyModal(self.ctx, self.helper, self.filepath, self.platform))

        @discord.ui.button(label="Save file", style=discord.ButtonStyle.green, custom_id="SaveFile_GTAV")
        async def save_file_callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(embed=embDone_G, view=None)
            if self.platform == "pc":
                await crypt.encrypt_file(self.filepath, crypt.GTAV_PC_HEADER_OFFSET)
            self.helper.done = True

    @staticmethod
    async def init_savefile(filepath: str) -> str | None:
        try:
            async with aiofiles.open(filepath, "rb") as file:
                await file.seek(crypt.GTAV_PC_HEADER_OFFSET)
                check_bytes = await file.read(4)

                if check_bytes == b"\x00\x00\x00\x00": # ps4 if true
                    platform = "ps4"
                    await file.seek(crypt.GTAV_PS_HEADER_OFFSET)
                    header = await file.read(len(crypt.GTAV_HEADER))

                else: # pc if true or invalid 
                    platform = "pc"
                    header = await file.read(len(crypt.GTAV_HEADER))
        except (ValueError, IOError, IndexError):
            raise QuickCheatsError("File not supported!")

        encrypted == header != crypt.GTAV_HEADER

        if encrypted:
            start_offset = crypt.GTAV_PS_HEADER_OFFSET if platform == "ps4" else crypt.GTAV_PC_HEADER_OFFSET
            try:
                await crypt.decrypt_file(filepath, start_offset)
            except (ValueError, IOError, IndexError):
                raise QuickCheatsError("File not supported!")
        return platform 

    @staticmethod
    async def change_money(filepath: str, money: int, character: str, platform: Literal["ps4", "pc"]) -> None:
        if money > Cheats_GTAV.MONEY_LIMIT or money < 0:
            raise QuickCheatsError(f"Invalid money limit, maximum is {Cheats_GTAV.MONEY_LIMIT: ,} and it must be positive.")

        try:
            async with QuickCheats(filepath) as qc:
                money_offset = await qc.find_off_with_identifier32(Cheats_GTAV.MONEY_OFFSET_IDENTIFIER_BEFORE[character], None, Cheats_GTAV.BYTES_BETWEEN_IDENTIFIER)
                if money_offset == -1:
                    raise QuickCheatsError("File not supported!")

                await qc.w_stream.seek(money_offset)
                money = uint32(money, "big")
                await qc.w_stream.write(money.as_bytes)

            start_offset = crypt.GTAV_PS_HEADER_OFFSET if platform == "ps4" else crypt.GTAV_PC_HEADER_OFFSET
            await crypt.encrypt_file(filepath, start_offset)
            await crypt.decrypt_file(filepath, start_offset) 
        except (ValueError, IOError, IndexError):
            raise QuickCheatsError("File not supported!")

    @staticmethod
    async def fetch_stats(filepath: str, platform: Literal["ps4", "pc"]) -> dict[str, int | str]:
        values = {}
        try:
            async with QuickCheats(filepath) as qc:
                for key, value in Cheats_GTAV.MONEY_OFFSET_IDENTIFIER_BEFORE.items():
                    money_offset = await qc.find_off_with_identifier32(value, None, Cheats_GTAV.BYTES_BETWEEN_IDENTIFIER)
                    await qc.r_stream.seek(money_offset)
                    money = uint32(await qc.r_stream.read(4), "big") 
                    values[key + "_cash"] = money.value
        except (ValueError, IOError, IndexError):
            raise QuickCheatsError("File not supported!")

        values["Platform"] = platform
        return values

    @staticmethod
    def loaded_embed(stats: dict[str, int | str]) -> discord.Embed:
        emb = embchgtav.copy()
        emb.description = emb.description.format(
            platform=stats["Platform"],
            franklin_cash=stats["Franklin_cash"],
            michael_cash=stats["Michael_cash"],
            trevor_cash=stats["Trevor_cash"]
        )
        return emb
