import discord
import os
import asyncio
from discord.ext import commands
from discord import Option
from data.converter import ConverterError
from google_drive.gd_functions import gdapi, GDapiError, HTTPError
from utils.namespaces import Converter
from utils.constants import (
    BASE_ERROR_MSG, SHARED_GD_LINK_DESC, MAX_FILES, ZIPOUT_NAME, COMMAND_COOLDOWN,
    logger, Color, Embed_t,
    embTimedOut
)
from utils.workspace import initWorkspace, makeWorkspace, cleanupSimple
from utils.helpers import errorHandling, TimeoutHelper, DiscordContext, UploadOpt, UploadGoogleDriveChoice, upload2, send_final
from utils.extras import completed_print
from utils.exceptions import FileError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class Convert(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Convert a ps4 savefile to pc or vice versa on supported games that needs converting.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def convert(
              self, 
              ctx: discord.ApplicationContext, 
              game: Option(str, choices=["GTA V", "RDR 2", "BL 3", "TTWL"], description="Choose what game the savefile belongs to."), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except (WorkspaceError, discord.HTTPException): return

        emb_conv_upl = discord.Embed(
            title=f"Conversion process: {game}",
            description=f"Please attach atleast 1 savefile. Or type 'EXIT' to cancel command.",
            colour=Color.DEFAULT.value
        )
        emb_conv_upl.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, True)

        try:
            await ctx.respond(embed=emb_conv_upl)
            msg = await ctx.edit(embed=emb_conv_upl)
            msg = await ctx.fetch_message(msg.id)
            d_ctx = DiscordContext(ctx, msg)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_DECRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False, ignore_filename_check=False, opt=opt)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (TimeoutError, GDapiError, FileError, TaskCancelledError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        
        batches = len(uploaded_file_paths)

        i = 1
        for entry in uploaded_file_paths:
            count_entry = len(entry)
            completed = []
            dname = os.path.dirname(entry[0])
            out_path = dname
            rand_str = os.path.basename(dname)
            
            j = 1
            for savegame in entry:
                basename = os.path.basename(savegame)
                emb_conv_choice = discord.Embed(
                    title=f"Converter: Choice ({basename})",
                    description=f"Could not recognize the platform of the save, please choose what platform to convert the save to (file {j}/{count_entry}, batch {i}/{batches}).",
                    colour=Color.DEFAULT.value
                )
                emb_conv_choice.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                try:
                    match game:
                        case "GTA V":
                            result = await Converter.Rstar.convertFile_GTAV(savegame)
                    
                        case "RDR 2":
                            result = await Converter.Rstar.convertFile_RDR2(savegame)

                        case "BL 3":
                            helper = TimeoutHelper(embTimedOut)
                            result = await Converter.BL3.convertFile(ctx, helper, savegame, False, emb_conv_choice)
                        
                        case "TTWL":
                            helper = TimeoutHelper(embTimedOut)
                            result = await Converter.BL3.convertFile(ctx, helper, savegame, True, emb_conv_choice)
                
                except ConverterError as e:
                    await errorHandling(ctx, e, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

                ret = True
                if result == "TIMED OUT":
                    embCDone = discord.Embed(title="TIMED OUT!", colour=Color.DEFAULT.value)
                elif result == "ERROR":
                    embCDone = discord.Embed(title="ERROR!", description="Invalid save!", colour=Color.DEFAULT.value)
                else:
                    embCDone = discord.Embed(
                        title="Success",
                        description=f"{result}\n**{basename}** (file {j}/{count_entry}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    ret = False
                embCDone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                try:
                    await msg.edit(embed=embCDone)
                except discord.HTTPException as e:
                    logger.exception(f"Error while editing msg: {e}")

                await asyncio.sleep(1)
                if ret:
                    await cleanupSimple(workspaceFolders)
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                completed.append(basename)
                j += 1

            finished_files = completed_print(completed)

            embCompleted = discord.Embed(
                title="Success!",
                description=(
                    f"Converted **{finished_files}** (batch {i}/{batches}).\n"
                    "Uploading file...\n"
                    "If file is being uploaded to Google Drive, you can send 'EXIT' to cancel."
                ),
                colour=Color.DEFAULT.value
            )
            embCompleted.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embCompleted)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = "savegame_Converted" + f"_{rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, out_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                await errorHandling(msg, e, workspaceFolders, None, None, None)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return
            except Exception as e:
                await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            await asyncio.sleep(1)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Convert(bot))