import discord
import asyncio
from io import BytesIO
from discord import Option
from discord.ext import commands
from utils.workspace import makeWorkspace, WorkspaceError
from utils.helpers import errorHandling
from utils.constants import logger, Color, Embed_t, SYS_FILE_MAX, BASE_ERROR_MSG, SAVEBLOCKS_MAX, loadSFO_emb, finished_emb
from utils.orbis import SFOContext, OrbisError

class SFO_Editor(SFOContext):
    """Discord utilities to parse and patch param.sfo."""
    def __init__(self, sfo_data: bytearray) -> None:
        super().__init__()
        self.sfo_data = sfo_data
    
    def read(self) -> None:
        self.sfo_read(self.sfo_data)
        self.param_data = self.sfo_get_param_data()
    
    def write(self) -> None:
        self.sfo_data = self.sfo_write()

    def dict_embed(self) -> list[discord.Embed]:
        embeds = []
        p_data = self.param_data.copy()
        for param in p_data:
            paramEmb = discord.Embed(colour=Color.DEFAULT.value)
            for key, val in param.items():
                if key == "value":
                    continue
                paramEmb.add_field(
                    name=key.upper(),
                    value=val,
                    inline=True
                )
            paramEmb.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            embeds.append(paramEmb)

        return embeds

class SFO(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    sfo_group = discord.SlashCommandGroup("sfo")

    @sfo_group.command(description="Parse a param.sfo file to obtain information about the save.")
    async def read(self, ctx: discord.ApplicationContext, sfo: discord.Attachment) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        await ctx.respond(embed=loadSFO_emb)

        if sfo.size / (1024 * 1024) > SYS_FILE_MAX:
            e = "File size is too large!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        sfo_data = bytearray(await sfo.read())

        try:
            sfo_ctx = SFO_Editor(sfo_data)
            sfo_ctx.read()
            param_embeds = sfo_ctx.dict_embed()
            for emb in param_embeds:
                await asyncio.sleep(1)
                await ctx.send(embed=emb)
            await ctx.edit(embed=finished_emb)
        except OrbisError as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return

    @sfo_group.command(description="Patch parameters in a param.sfo file to modify the save.")
    async def write(
              self, 
              ctx: discord.ApplicationContext, 
              sfo: discord.Attachment,
              account_id: Option(str, description="uint64 (hexadecimal)", default="", max_length=2 + 16), # type: ignore
              attribute: Option(int, description="uint32", default="", min_value=0, max_value=0xFF_FF_FF_FF), # type: ignore
              category: Option(str, description="utf-8", default=""), # type: ignore
              detail: Option(str, description="utf-8", default=""), # type: ignore
              format: Option(str, description="utf-8", default=""), # type: ignore
              maintitle: Option(str, description="utf-8", default=""), # type: ignore
              params: Option(str, description="utf-8-special", default=""), # type: ignore
              savedata_blocks: Option(int, description="uint64", default="", min_value=1, max_value=SAVEBLOCKS_MAX), # type: ignore
              savedata_directory: Option(str, description="utf-8", default=""), # type: ignore
              savedata_list_param: Option(int, description="uint32", default="", min_value=0, max_value=0xFF_FF_FF_FF), # type: ignore
              subtitle: Option(str, description="utf-8", default=""), # type: ignore
              title_id: Option(str, description="utf-8", default="") # type: ignore
            ) -> None:
        
        parameters = {
            "ACCOUNT_ID": account_id,
            "ATTRIBUTE": attribute,
            "CATEGORY": category,
            "DETAIL": detail,
            "FORMAT": format,
            "MAINTITLE": maintitle,
            "PARAMS": params,
            "SAVEDATA_BLOCKS": savedata_blocks,
            "SAVEDATA_DIRECTORY": savedata_directory,
            "SAVEDATA_LIST_PARAM": savedata_list_param,
            "SUBTITLE": subtitle,
            "TITLE_ID": title_id
        }
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        await ctx.respond(embed=loadSFO_emb)

        if sfo.size / (1024 * 1024) > SYS_FILE_MAX:
            e = "File size is too large!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        sfo_data = bytearray(await sfo.read())

        try:
            sfo_ctx = SFO_Editor(sfo_data)
            sfo_ctx.read()
            for key, val in parameters.items():
                if not val: 
                    continue
                sfo_ctx.sfo_patch_parameter(key, val)
            sfo_ctx.write()

            await ctx.edit(embed=finished_emb)
            await ctx.respond(file=discord.File(BytesIO(sfo_ctx.sfo_data), filename=sfo.filename))
        except OrbisError as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            if isinstance(e, ValueError):
                err = "Invalid value inputted!"
            else:
                err = BASE_ERROR_MSG
            await errorHandling(ctx, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return

        # cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(SFO(bot))