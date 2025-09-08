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
    logger
)
from utils.embeds import (
    embTimedOut, emb_conv_upl, emb_conv_choice, 
    embCDone1, embCDone2, embCDone3, embconvCompleted
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

        emb = emb_conv_upl.copy()
        emb.title = emb.title.format(game=game)

        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, True)

        try:
            await ctx.respond(embed=emb)
            msg = await ctx.edit(embed=emb)
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
                emb = emb_conv_choice.copy()
                emb.title = emb.title.format(basename=basename)
                emb.description = emb.description.format(j=j, count_entry=count_entry, i=i, batches=batches)
                try:
                    match game:
                        case "GTA V":
                            result = await Converter.Rstar.convertFile_GTAV(savegame)
                    
                        case "RDR 2":
                            result = await Converter.Rstar.convertFile_RDR2(savegame)

                        case "BL 3":
                            helper = TimeoutHelper(embTimedOut)
                            result = await Converter.BL3.convertFile(ctx, helper, savegame, False, emb)
                        
                        case "TTWL":
                            helper = TimeoutHelper(embTimedOut)
                            result = await Converter.BL3.convertFile(ctx, helper, savegame, True, emb)
                
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
                    emb = embCDone1
                elif result == "ERROR":
                    emb = embCDone2
                else:
                    emb = embCDone3.copy()
                    emb.description = emb.description.format(result=result, basename=basename, j=j, count_entry=count_entry, i=i, batches=batches)
                    ret = False
                try:
                    await msg.edit(embed=emb)
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

            emb = embconvCompleted.copy()
            emb.description = emb.description.format(finished_files=finished_files, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = "savegame_Converted" + f"_{rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, out_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                if isinstance(e, discord.HTTPException):
                    e = BASE_ERROR_MSG
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