import discord
import os
from discord.ext import commands
from discord import Option
from data.converter import ConverterError
from utils.namespaces import Converter
from utils.constants import (
    BOT_DISCORD_UPLOAD_LIMIT, BASE_ERROR_MSG,
    logger, Color, Embed_t,
    embTimedOut 
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanupSimple
from utils.helpers import errorHandling, TimeoutHelper

class Convert(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Convert a ps4 savefile to pc or vice versa on supported games that needs converting.")
    async def convert(
              self, 
              ctx: discord.ApplicationContext, 
              game: Option(str, choices=["GTA V", "RDR 2", "BL 3", "TTWL"], description="Choose what game the savefile belongs to."), # type: ignore
              savefile: discord.Attachment
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        embConverting = discord.Embed(
            title="Converting",
            description=f"Starting convertion process for {game}...",
            colour=Color.DEFAULT.value
        )
        embConverting.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        await ctx.respond(embed=embConverting)

        if savefile.size / (1024 * 1024) > BOT_DISCORD_UPLOAD_LIMIT:
            e = "File size is too large!" # may change in the future when a game with larger savefile sizes are implemented
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        savegame = os.path.join(newUPLOAD_DECRYPTED, savefile.filename)
        await savefile.save(savegame)

        try:
            match game:
                case "GTA V":
                    result = await Converter.Rstar.convertFile_GTAV(savegame)
            
                case "RDR 2":
                    result = await Converter.Rstar.convertFile_RDR2(savegame)

                case "BL 3":
                    helper = TimeoutHelper(embTimedOut)
                    result = await Converter.BL3.convertFile(ctx, helper, savegame, False)
                
                case "TTWL":
                    helper = TimeoutHelper(embTimedOut)
                    result = await Converter.BL3.convertFile(ctx, helper, savegame, True)
        
        except ConverterError as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        if result == "TIMED OUT":
            embCDone = discord.Embed(title="TIMED OUT!", colour=Color.DEFAULT.value)
        elif result == "ERROR":
            embCDone = discord.Embed(title="ERROR!", description="Invalid save!", colour=Color.DEFAULT.value)
        else:
            embCDone = discord.Embed(
                title="Success",
                description=f"{result}\nPlease report any errors.",
                colour=Color.DEFAULT.value
            )
        embCDone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        await ctx.edit(embed=embCDone)
        await ctx.respond(file=discord.File(savegame))

        cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Convert(bot))