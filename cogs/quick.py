import discord
import asyncio
import os
import shutil
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapiError
from data.cheats import QuickCodes, QuickCodesError, QuickCheatsError
from utils.constants import (
    IP, PORT, PS_UPLOADDIR, PORTSOCKET, MAX_FILES, BOT_DISCORD_UPLOAD_LIMIT, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC,
    logger, Color,
    emb_upl_savegame, embhttp, embTimedOut
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, listStoredSaves
from utils.extras import generate_random_string
from utils.helpers import psusername, upload2, errorHandling, TimeoutHelper, send_final
from utils.orbis import OrbisError
from utils.exceptions import PSNIDError
from utils.namespaces import Cheats

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
        except: return
        C1ftp = FTPps(IP, PORT, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORTSOCKET)
        mountPaths = []
        
        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            response = await listStoredSaves(ctx)
        except (PSNIDError, TimeoutError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        if response == "EXIT":
            embExit = discord.Embed(title="Exited.", colour=Color.DEFAULT.value)
            embExit.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embExit)
            cleanupSimple(workspaceFolders)
            return
        
        random_string = generate_random_string(RANDOMSTRING_LENGTH)
        saveName = os.path.basename(response)
        files = await aiofiles.os.listdir(newUPLOAD_ENCRYPTED)
        realSave = f"{saveName}_{random_string}"

        try:
            shutil.copyfile(response, os.path.join(newUPLOAD_ENCRYPTED, f"{saveName}_{random_string}"))
            shutil.copyfile(response + ".bin", os.path.join(newUPLOAD_ENCRYPTED, f"{saveName}_{random_string}.bin"))

            emb4 = discord.Embed(title="Resigning process: Encrypted",
                        description=f"Your save (**{saveName}**) is being resigned, please wait...",
                        colour=Color.DEFAULT.value)
            emb4.set_footer(text="Made by hzh.")

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

            emb5 = discord.Embed(title="Resigning process (Encrypted): Successful",
                        description=f"**{saveName}** resigned to **{playstation_id or user_id}**",
                        colour=Color.DEFAULT.value)
            emb5.set_footer(text="Made by hzh.")

            await ctx.edit(embed=emb5)

        except (SocketError, FTPError, OrbisError, OSError) as e:
            if isinstance(e, OSError) and hasattr(e, "winerror") and e.winerror == 121: 
                e = "PS4 not connected!"
            elif isinstance(e, OrbisError): 
                logger.error(f"{response} is a invalid save") # If OrbisError is raised you have stored an invalid save
            await errorHandling(ctx, e, workspaceFolders, files, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, files, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        embRdone = discord.Embed(title="Resigning process (Encrypted): Successful",
                                description=f"**{saveName}** resigned to **{playstation_id or user_id}**.",
                                colour=Color.DEFAULT.value)
        embRdone.set_footer(text="Made by hzh.")
        
        await ctx.edit(embed=embRdone)

        try: 
            await send_final(ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
        except HTTPError as e:
            errmsg = "HTTPError while uploading file to Google Drive, if problem reoccurs storage may be full."
            await errorHandling(ctx, errmsg, workspaceFolders, files, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return

        # await asyncio.sleep(1)
        await cleanup(C1ftp, workspaceFolders, files, mountPaths)

    @quick_group.command(description="Apply save wizard quick codes to your save.")
    async def codes(
              self, 
              ctx: discord.ApplicationContext, 
              codes: str, 
              endianness: Option(str, choices=["little", "big"], description="Little is default, if little does not work use this option and try big.", default="little") # type: ignore
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        await ctx.respond(embed=emb_upl_savegame)

        try:
            uploaded_file_paths = await upload2(ctx, newUPLOAD_DECRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False)
        except HTTPError as e:
            await ctx.edit(embed=embhttp)
            cleanupSimple(workspaceFolders)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (TimeoutError, GDapiError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        completed = []

        if len(uploaded_file_paths) >= 1:
            savefiles = await aiofiles.os.listdir(newUPLOAD_DECRYPTED)

            for savefile in savefiles:
                savegame = os.path.join(newUPLOAD_DECRYPTED, savefile)
                
                embLoading = discord.Embed(title="Loading",
                                    description=f"Loading {savefile}...",
                                    colour=Color.DEFAULT.value)
                embLoading.set_footer(text="Made by hzh.")

                embApplied = discord.Embed(title="Success!",
                                    description=f"Quick codes applied to {savefile}.",
                                    colour=Color.DEFAULT.value)
                embApplied.set_footer(text="Made by hzh.")

                await ctx.edit(embed=embLoading)

                try:
                    qc = QuickCodes(savegame, codes, endianness)
                    await qc.apply_code()  
                except QuickCodesError as e:
                    e = f"**{str(e)}**" + "\nThe code has to work on all the savefiles you uploaded!"
                    await errorHandling(ctx, e, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    return
                except Exception as e:
                    await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return
        
                await ctx.edit(embed=embApplied)
                completed.append(savefile)

        if len(completed) == 1:
            finishedFiles = "".join(completed)
        else: finishedFiles = ", ".join(completed)

        embCompleted = discord.Embed(title="Success!",
                                    description=f"Quick codes applied to {finishedFiles}.",
                                    colour=Color.DEFAULT.value)
        embCompleted.set_footer(text="Made by hzh.")
        await ctx.edit(embed=embCompleted)

        try: 
            await send_final(ctx, "savegame_CodeApplied.zip", newUPLOAD_DECRYPTED)
        except HTTPError as e:
            errmsg = "HTTPError while uploading file to Google Drive, if problem reoccurs storage may be full."
            await errorHandling(ctx, errmsg, workspaceFolders, None, None, None)
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

        embLoading = discord.Embed(title="Loading",
                            description=f"Loading cheats process for {game}...",
                            colour=Color.DEFAULT.value)
        embLoading.set_footer(text="Made by hzh.")

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