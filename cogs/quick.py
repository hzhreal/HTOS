import discord
import asyncio
import os
import shutil
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from data.cheats import QuickCodes, QuickCodesError, QuickCheatsError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BOT_DISCORD_UPLOAD_LIMIT, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    emb_upl_savegame, embTimedOut, working_emb
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, listStoredSaves
from utils.extras import generate_random_string
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, TimeoutHelper, send_final, run_qr_paginator
from utils.orbis import OrbisError
from utils.exceptions import PSNIDError
from utils.namespaces import Cheats
from utils.exceptions import FileError

class Quick(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    quick_group = discord.SlashCommandGroup("quick")

    @quick_group.command(description="Resign pre stored saves.")
    async def resign(self, ctx: discord.ApplicationContext, playstation_id: Option(str, description=PS_ID_DESC, default="")) -> None: # type: ignore
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

            msg = await ctx.edit(embed=working_emb)
            msg = await ctx.fetch_message(msg.id) # fetch for paginator.edit()
            d_ctx = DiscordContext(ctx, msg)
            stored_saves = await listStoredSaves()
            response = await run_qr_paginator(d_ctx, stored_saves)
        except (PSNIDError, WorkspaceError, TimeoutError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return

        if response == "EXIT":
            embExit = discord.Embed(title="Exited.", colour=Color.DEFAULT.value)
            embExit.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embExit, view=None)
            cleanupSimple(workspaceFolders)
            return

        random_string = generate_random_string(RANDOMSTRING_LENGTH)
        saveName = os.path.basename(response)
        realSave = f"{saveName}_{random_string}"
        uploaded_file_paths = [realSave, realSave + ".bin"]

        try:
            shutil.copyfile(response, os.path.join(newUPLOAD_ENCRYPTED, realSave))
            shutil.copyfile(response + ".bin", os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))

            emb4 = discord.Embed(
                title="Resigning process: Encrypted",
                description=f"Your save (**{saveName}**) is being resigned, please wait...",
                colour=Color.DEFAULT.value
            )
            emb4.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            await ctx.edit(embed=emb4)
            await C1ftp.uploadencrypted_bulk(realSave)
            mount_location_new = MOUNT_LOCATION + "/" + random_string
            await C1ftp.make1(mount_location_new)
            mountPaths.append(mount_location_new)
            await C1socket.socket_dump(mount_location_new, realSave)
            location_to_scesys = mount_location_new + "/sce_sys"
            await C1ftp.dlparam(location_to_scesys, user_id)
            await C1socket.socket_update(mount_location_new, realSave)
            await C1ftp.dlencrypted_bulk(False, user_id, realSave)

            emb5 = discord.Embed(
                title="Resigning process (Encrypted): Successful",
                description=f"**{saveName}** resigned to **{playstation_id or user_id}**",
                colour=Color.DEFAULT.value
            )
            emb5.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            await ctx.edit(embed=emb5)

        except (SocketError, FTPError, OrbisError, OSError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            elif isinstance(e, OrbisError): 
                logger.error(f"{response} is a invalid save") # If OrbisError is raised you have stored an invalid save

            await errorHandling(d_ctx.msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - ({status})")
            return
        except Exception as e:
            await errorHandling(d_ctx.msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        embRdone = discord.Embed(
            title="Resigning process (Encrypted): Successful",
            description=f"**{saveName}** resigned to **{playstation_id or user_id}**.",
            colour=Color.DEFAULT.value
        )
        embRdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        
        await ctx.edit(embed=embRdone)

        try: 
            await send_final(d_ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
        except GDapiError as e:
            await errorHandling(d_ctx.msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return

        # await asyncio.sleep(1)
        await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

    @quick_group.command(description="Apply save wizard quick codes to your save.")
    async def codes(
              self, 
              ctx: discord.ApplicationContext, 
              codes: str, 
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

        try:
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_DECRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        completed = []

        if len(uploaded_file_paths) >= 1:
            savefiles = await aiofiles.os.listdir(newUPLOAD_DECRYPTED)

            for savefile in savefiles:
                savegame = os.path.join(newUPLOAD_DECRYPTED, savefile)
                
                embLoading = discord.Embed(
                    title="Loading",
                    description=f"Loading {savefile}...",
                    colour=Color.DEFAULT.value
                )
                embLoading.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                embApplied = discord.Embed(
                    title="Success!",
                    description=f"Quick codes applied to {savefile}.",
                    colour=Color.DEFAULT.value
                )
                embApplied.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                await msg.edit(embed=embLoading)

                try:
                    qc = QuickCodes(savegame, codes)
                    await qc.apply_code()  
                except QuickCodesError as e:
                    e = f"**{str(e)}**" + "\nThe code has to work on all the savefiles you uploaded!"
                    await errorHandling(msg, e, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return
        
                await msg.edit(embed=embApplied)
                completed.append(savefile)

        if len(completed) == 1:
            finishedFiles = "".join(completed)
        else: finishedFiles = ", ".join(completed)

        embCompleted = discord.Embed(
            title="Success!",
            description=f"Quick codes applied to {finishedFiles}.",
            colour=Color.DEFAULT.value
        )
        embCompleted.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        await msg.edit(embed=embCompleted)

        try: 
            await send_final(d_ctx, "savegame_CodeApplied.zip", newUPLOAD_DECRYPTED)
        except GDapiError as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return

        await asyncio.sleep(1)
        cleanupSimple(workspaceFolders)
    
    @quick_group.command(description="Add cheats to your save.")
    async def cheats(self, ctx: discord.ApplicationContext, game: Option(str, choices=["GTA V", "RDR 2"]), savefile: discord.Attachment) -> None: # type: ignore
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        embLoading = discord.Embed(
            title="Loading",
            description=f"Loading cheats process for {game}...",
            colour=Color.DEFAULT.value
        )
        embLoading.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        await ctx.respond(embed=embLoading)

        if savefile.size / (1024 * 1024) > BOT_DISCORD_UPLOAD_LIMIT:
            e = "File size is too large!" # may change in the future when a game with larger savefile sizes are implemented
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
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
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        await ctx.respond(file=discord.File(savegame))
        await asyncio.sleep(1)

        cleanupSimple(workspaceFolders)
    
def setup(bot: commands.Bot) -> None:
    bot.add_cog(Quick(bot))