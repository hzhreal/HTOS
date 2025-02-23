import discord
import asyncio
import os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from data.cheats import QuickCodes, QuickCodesError, QuickCheatsError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BOT_DISCORD_UPLOAD_LIMIT, BASE_ERROR_MSG, ZIPOUT_NAME, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    emb_upl_savegame, embTimedOut, working_emb
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple, listStoredSaves
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, TimeoutHelper, send_final, run_qr_paginator, UploadGoogleDriveChoice, UploadOpt, ReturnTypes
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError
from utils.namespaces import Cheats
from utils.extras import completed_print
from utils.exceptions import FileError, OrbisError, WorkspaceError
from utils.instance_lock import INSTANCE_LOCK_global

class Quick(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    quick_group = discord.SlashCommandGroup("quick")

    @quick_group.command(description="Resign pre stored saves.")
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
        except WorkspaceError: return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORT_CECIE)
        mountPaths = []
        
        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await GDapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=working_emb)
            msg = await ctx.fetch_message(msg.id) # fetch for paginator.edit()
            d_ctx = DiscordContext(ctx, msg)
            stored_saves = await listStoredSaves()
            res, savepaths = await run_qr_paginator(d_ctx, stored_saves)
        except (PSNIDError, WorkspaceError, TimeoutError, GDapiError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release()
            return

        if res == ReturnTypes.EXIT:
            embExit = discord.Embed(title="Exited.", colour=Color.DEFAULT.value)
            embExit.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embExit, view=None)
            await cleanupSimple(workspaceFolders)
            await INSTANCE_LOCK_global.release()
            return

        entry = []
        batch = SaveBatch(C1ftp, C1socket, user_id, [], mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)

        try:
            for path in savepaths:
                target_path = os.path.join(newUPLOAD_ENCRYPTED, os.path.basename(path))
                shutil.copyfile(path, target_path)
                shutil.copyfile(path + ".bin", target_path + ".bin")
                entry.append(target_path)
                entry.append(target_path + ".bin")

            batch.entry = entry
            await batch.construct()

            i = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                await savefile.construct()

                emb4 = discord.Embed(
                    title="Resigning process: Encrypted",
                    description=f"Your save (**{savefile.basename}**) is being resigned ({i}/{batch.savecount}), please wait...",
                    colour=Color.DEFAULT.value
                )
                emb4.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=emb4)

                await savefile.dump()
                await savefile.resign()

                emb5 = discord.Embed(
                    title="Resigning process (Encrypted): Successful",
                    description=f"**{savefile.basename}** resigned to **{playstation_id or user_id}** ({i}/{batch.savecount}).",
                    colour=Color.DEFAULT.value
                )
                emb5.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=emb5)
                i += 1

        except (SocketError, FTPError, OrbisError, OSError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            elif isinstance(e, OrbisError): 
                logger.error(f"There is invalid save(s) in {savepaths}") # If OrbisError is raised you have stored an invalid save

            await errorHandling(d_ctx.msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - ({status})")
            await INSTANCE_LOCK_global.release()
            return
        except Exception as e:
            await errorHandling(d_ctx.msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release()
            return
        
        embRdone = discord.Embed(
            title="Resigning process (Encrypted): Successful",
            description=f"**{batch.printed}** resigned to **{playstation_id or user_id}**.",
            colour=Color.DEFAULT.value
        )
        embRdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        await ctx.edit(embed=embRdone)

        zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}_1" + ZIPOUT_NAME[1]

        try: 
            await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
        except GDapiError as e:
            await errorHandling(d_ctx.msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return

        await cleanup(C1ftp, workspaceFolders, batch.entry, mountPaths)
        await INSTANCE_LOCK_global.release()

    @quick_group.command(description="Apply save wizard quick codes to your save.")
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
        except WorkspaceError: return

        await ctx.respond(embed=emb_upl_savegame)
        msg = await ctx.edit(embed=emb_upl_savegame)
        msg = await ctx.fetch_message(msg.id)
        d_ctx = DiscordContext(ctx, msg)

        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, True)

        try:
            shared_gd_folderid = await GDapi.parse_sharedfolder_link(shared_gd_link)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_DECRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False, ignore_filename_check=False, opt=opt)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except (TimeoutError, GDapiError, FileError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release()
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
                
                embLoading = discord.Embed(
                    title="Loading",
                    description=f"Loading **{basename}**... (file {j}/{count_entry}, batch {i}/{batches}).",
                    colour=Color.DEFAULT.value
                )
                embLoading.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await msg.edit(embed=embLoading)

                try:
                    qc = QuickCodes(savegame, codes)
                    await qc.apply_code()
                except QuickCodesError as e:
                    e = f"**{str(e)}**" + "\nThe code has to work on all the savefiles you uploaded!"
                    await errorHandling(msg, e, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    await INSTANCE_LOCK_global.release()
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release()
                    return

                embApplied = discord.Embed(
                    title="Success!",
                    description=f"Quick codes applied to **{basename}** (file {j}/{count_entry}, batch {i}/{batches}).",
                    colour=Color.DEFAULT.value
                )
                embApplied.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await msg.edit(embed=embApplied)
                completed.append(basename)
                j += 1

            finished_files = completed_print(completed)

            embCompleted = discord.Embed(
                title="Success!",
                description=f"Quick codes applied to **{finished_files}** ({i}/{batches}).",
                colour=Color.DEFAULT.value
            )
            embCompleted.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embCompleted)

            zipname = "savegame_CodeApplied" + f"_{rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, out_path, shared_gd_folderid)
            except GDapiError as e:
                await errorHandling(msg, e, workspaceFolders, None, None, None)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release()
                return

            await asyncio.sleep(1)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release()
    
    @quick_group.command(description="Add cheats to your save.")
    async def cheats(self, ctx: discord.ApplicationContext, game: Option(str, choices=["GTA V", "RDR 2"]), savefile: discord.Attachment) -> None: # type: ignore
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        embLoading = discord.Embed(
            title="Loading",
            description=f"Loading cheats process for **{game}**...",
            colour=Color.DEFAULT.value
        )
        embLoading.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        await ctx.respond(embed=embLoading)

        if savefile.size > BOT_DISCORD_UPLOAD_LIMIT:
            e = "File size is too large!" # may change in the future when a game with larger savefile sizes are implemented
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            await INSTANCE_LOCK_global.release()
            return

        savegame = os.path.join(newUPLOAD_DECRYPTED, savefile.filename)
        await savefile.save(savegame)

        helper = TimeoutHelper(embTimedOut)

        try:
            match game:
                case "GTA V":
                    platform = await Cheats.GTAV.initSavefile(savegame)
                    stats = await Cheats.GTAV.fetchStats(savegame, platform)
                    embLoaded = Cheats.GTAV.loaded_embed(stats)
                    await ctx.edit(embed=embLoaded, view=Cheats.GTAV.CheatsButton(ctx, helper, savegame, platform))
                case "RDR 2":
                    platform = await Cheats.RDR2.initSavefile(savegame)
                    stats = await Cheats.RDR2.fetchStats(savegame, platform)
                    embLoaded = Cheats.RDR2.loaded_embed(stats)
                    await ctx.edit(embed=embLoaded, view=Cheats.RDR2.CheatsButton(ctx, helper, savegame, platform))
            await helper.await_done()
        
        except QuickCheatsError as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release()
            return
        
        await ctx.respond(file=discord.File(savegame))
        await asyncio.sleep(1)

        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release()
    
def setup(bot: commands.Bot) -> None:
    bot.add_cog(Quick(bot))