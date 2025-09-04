import discord
import asyncio
import os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, C1socket, FTPError, SocketError
from google_drive import gdapi, GDapiError
from data.cheats import QuickCodes, QuickCodesError, QuickCheatsError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BOT_DISCORD_UPLOAD_LIMIT, BASE_ERROR_MSG, ZIPOUT_NAME, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, COMMAND_COOLDOWN,
    logger
)
from utils.embeds import (
    emb_upl_savegame, embTimedOut, working_emb, embExit, 
    embresb, embresbs, embRdone, embLoading, embApplied,
    embqcCompleted, embchLoading
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple, listStoredSaves
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, TimeoutHelper, send_final, run_qr_paginator, UploadGoogleDriveChoice, UploadOpt, ReturnTypes, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError
from utils.namespaces import Cheats
from utils.extras import completed_print
from utils.exceptions import FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class Quick(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    quick_group = discord.SlashCommandGroup("quick")

    @quick_group.command(description="Resign pre stored saves.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def resign(
              self, 
              ctx: discord.ApplicationContext, 
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except (WorkspaceError, discord.HTTPException): return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mountPaths = []

        msg = ctx
        
        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=working_emb)
            msg = await ctx.fetch_message(msg.id) # fetch for paginator.edit()
            d_ctx = DiscordContext(ctx, msg)
            stored_saves = await listStoredSaves()
            res, savepaths = await run_qr_paginator(d_ctx, stored_saves)
        except (PSNIDError, WorkspaceError, TimeoutError, GDapiError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        if res == ReturnTypes.EXIT:
            try:
                await msg.edit(embed=embExit, view=None)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")
            await cleanupSimple(workspaceFolders)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        entry = []
        batch = SaveBatch(C1ftp, C1socket, user_id, entry, mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)

        try:
            for path in savepaths:
                target_path = os.path.join(newUPLOAD_ENCRYPTED, os.path.basename(path))
                shutil.copyfile(path, target_path)
                shutil.copyfile(path + ".bin", target_path + ".bin")
                entry.append(target_path)
                entry.append(target_path + ".bin")

            await batch.construct()

            i = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                await savefile.construct()

                emb = embresb.copy()
                emb.description = emb.description.format(savename=savefile.basename, i=i, savecount=batch.savecount)
                tasks = [
                    savefile.dump,
                    savefile.resign
                ]
                await task_handler(d_ctx, tasks, [emb])

                emb = embresbs.copy()
                emb.description = emb.description.format(savename=savefile.basename, id=playstation_id or user_id, i=i, savecount=batch.savecount)
                await msg.edit(embed=emb)
                i += 1
        except (SocketError, FTPError, OrbisError, OSError, TaskCancelledError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            elif isinstance(e, OrbisError): 
                logger.error(f"There is invalid save(s) in {savepaths}") # If OrbisError is raised you have stored an invalid save

            await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - ({status})")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        
        emb = embRdone.copy()
        emb.description = emb.description.format(printed=batch.printed, id=playstation_id or user_id)
        try:
            await msg.edit(embed=emb)
        except discord.HTTPException as e:
            logger.exception(f"Error while editing msg: {e}")

        zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}_1" + ZIPOUT_NAME[1]

        try: 
            await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
        except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
            if isinstance(e, discord.HTTPException):
                e = BASE_ERROR_MSG
            await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        await cleanup(C1ftp, workspaceFolders, batch.entry, mountPaths)
        await INSTANCE_LOCK_global.release(ctx.author.id)

    @quick_group.command(description="Apply save wizard quick codes to your save.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def codes(
              self, 
              ctx: discord.ApplicationContext, 
              codes: str,
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except (WorkspaceError, discord.HTTPException): return

        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, True)

        try:
            await ctx.respond(embed=emb_upl_savegame)
            msg = await ctx.edit(embed=emb_upl_savegame)
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
                
                emb1 = embLoading.copy()
                emb1.description.format(basename=basename, j=j, count_entry=count_entry, i=i, batches=batches)
                emb2 = embApplied.copy()
                emb2.description.format(basename=basename, j=j, count_entry=count_entry, i=i, batches=batches)

                try:
                    await msg.edit(embed=emb1)
                    qc = QuickCodes(savegame, codes)
                    await qc.apply_code()
                    await msg.edit(embed=emb2)
                except QuickCodesError as e:
                    e = f"**{str(e)}**" + "\nThe code has to work on all the savefiles you uploaded!"
                    await errorHandling(msg, e, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

                completed.append(basename)
                j += 1

            finished_files = completed_print(completed)

            emb = embqcCompleted.copy()
            emb.description = emb.description.format(finished_files=finished_files, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = "savegame_CodeApplied" + f"_{rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

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
    
    @quick_group.command(description="Add cheats to your save.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def cheats(self, ctx: discord.ApplicationContext, game: Option(str, choices=["GTA V", "RDR 2"]), savefile: discord.Attachment) -> None: # type: ignore
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id, skip_gd_check=True)
        except (WorkspaceError, discord.HTTPException): return

        emb = embchLoading.copy()
        emb.description = emb.description.format(game=game)
        try:
            await ctx.respond(embed=emb)
            msg = await ctx.edit(embed=emb)
            msg = await ctx.fetch_message(msg.id)
        except discord.HTTPException as e:
            logger.exception(e)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        if savefile.size > BOT_DISCORD_UPLOAD_LIMIT:
            e = "File size is too large!" # may change in the future when a game with larger savefile sizes are implemented
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        savegame = os.path.join(newUPLOAD_DECRYPTED, savefile.filename)
        helper = TimeoutHelper(embTimedOut)

        try:
            await savefile.save(savegame)

            match game:
                case "GTA V":
                    platform = await Cheats.GTAV.initSavefile(savegame)
                    stats = await Cheats.GTAV.fetchStats(savegame, platform)
                    embLoaded = Cheats.GTAV.loaded_embed(stats)
                    await msg.edit(embed=embLoaded, view=Cheats.GTAV.CheatsButton(ctx, helper, savegame, platform))
                case "RDR 2":
                    platform = await Cheats.RDR2.initSavefile(savegame)
                    stats = await Cheats.RDR2.fetchStats(savegame, platform)
                    embLoaded = Cheats.RDR2.loaded_embed(stats)
                    await msg.edit(embed=embLoaded, view=Cheats.RDR2.CheatsButton(ctx, helper, savegame, platform))
            await helper.await_done()

            await ctx.send(file=discord.File(savegame), reference=msg)
        except QuickCheatsError as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)
    
def setup(bot: commands.Bot) -> None:
    bot.add_cog(Quick(bot))