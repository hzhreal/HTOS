import discord
import asyncio
import aiofiles.os
import os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapiError
from utils.constants import (
    IP, PORT, PS_UPLOADDIR, PORTSOCKET, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC,
    logger, Color,
    embpng, embhttp, emb6, embpng1, embpng2, embTitleChange, embTitleErr
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames, pngprocess
from utils.helpers import psusername, upload2, errorHandling, send_final
from utils.orbis import handleTitles, OrbisError
from utils.exceptions import PSNIDError

class Change(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    change_group = discord.SlashCommandGroup("change")
    
    @change_group.command(description="Changes the picture of your save, this is just cosmetic.")
    async def picture(
              self, 
              ctx: discord.ApplicationContext, 
              picture: discord.Attachment, 
              playstation_id: Option(str, description=PS_ID_DESC, defualt="") # type: ignore
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return
        C1ftp = FTPps(IP, PORT, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORTSOCKET)
        mountPaths = []
        pngfile = os.path.join(newPNG_PATH, "icon0.png")
        size = (228, 128)

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            await ctx.edit(embed=embpng)
            uploaded_file_paths = await upload2(ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True)
        except HTTPError as e:
            await ctx.edit(embed=embhttp)
            cleanupSimple(workspaceFolders)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
                
        savenames = await obtain_savenames(newUPLOAD_ENCRYPTED)

        if len(uploaded_file_paths) >= 2:
            # png handling
            await picture.save(pngfile)
            pngprocess(pngfile, size)
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)
                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    await ctx.edit(embed=embpng1)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    await ctx.edit(embed=embpng2)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.swappng(location_to_scesys)
                    await C1ftp.dlparam(location_to_scesys, user_id)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    embpngs = discord.Embed(title="PNG process: Successful",
                                description=f"Altered the save png of **{save}**.",
                                colour=Color.DEFAULT.value)
                    embpngs.set_footer(text="Made by hzh.")

                    await ctx.edit(embed=embpngs)

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    if isinstance(e, OSError) and hasattr(e, "winerror") and e.winerror == 121: 
                        e = "PS4 not connected!"
                    await errorHandling(ctx, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    return
                except Exception as e:
                    await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return

            if len(savenames) == 1:
                finishedFiles = "".join(savenames)
            else: finishedFiles = ", ".join(savenames)

            embPdone = discord.Embed(title="PNG process: Successful",
                                description=f"Altered the save png of **{finishedFiles} and resigned to {playstation_id or user_id}**.",
                                colour=Color.DEFAULT.value)
            embPdone.set_footer(text="Made by hzh.")

            await ctx.edit(embed=embPdone)

            try: 
                await send_final(ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
            except HTTPError as e:
                errmsg = "HTTPError while uploading file to Google Drive, if problem reoccurs storage may be full."
                await errorHandling(ctx, errmsg, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return
            
            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

        else:
            await ctx.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

    @change_group.command(description="Change the titles of your save.")
    async def title(
              self, 
              ctx: discord.ApplicationContext, 
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              maintitle: Option(str, description="For example Grand Theft Auto V.", default=""), # type: ignore
              subtitle: Option(str, description="For example Franklin and Lamar (1.6%).", default="") # type: ignore
            ) -> None:
        
        if maintitle == "" and subtitle == "":
            await ctx.respond(embed=embTitleErr)
            return
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return
        C1ftp = FTPps(IP, PORT, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORTSOCKET)
        mountPaths = []

        try: 
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            await ctx.edit(embed=embTitleChange)
            uploaded_file_paths = await upload2(ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True)
        except HTTPError as e:
            await ctx.edit(embed=embhttp)
            cleanupSimple(workspaceFolders)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
                
        savenames = await obtain_savenames(newUPLOAD_ENCRYPTED)

        if len(uploaded_file_paths) >= 2:
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)

                embTitleChange1 = discord.Embed(title="Change title: Processing",
                                    description=f"Processing {save}.",
                                    colour=Color.DEFAULT.value)
                embTitleChange1.set_footer(text="Made by hzh.")

                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    await ctx.edit(embed=embTitleChange1)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparamonly_grab(location_to_scesys)
                    await handleTitles(newPARAM_PATH, user_id, maintitle, subtitle)
                    await C1ftp.upload_sfo(newPARAM_PATH, location_to_scesys)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    embTitleSuccess = discord.Embed(title="Title altering process: Successful",
                                description=f"Altered the save titles of **{save}**.",
                                colour=Color.DEFAULT.value)
                    embTitleSuccess.set_footer(text="Made by hzh.")

                    await ctx.edit(embed=embTitleSuccess)

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    if isinstance(e, OSError) and hasattr(e, "winerror") and e.winerror == 121: 
                        e = "PS4 not connected!"
                    await errorHandling(ctx, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    return
                except Exception as e:
                    await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return
            
            if len(savenames) == 1:
                finishedFiles = "".join(savenames)
            else: finishedFiles = ", ".join(savenames)

            embTdone = discord.Embed(title="Title altering process: Successful",
                                description=f"Altered the save titles of **{finishedFiles}**, and resigned to ***{playstation_id or user_id}**.",
                                colour=Color.DEFAULT.value)
            embTdone.set_footer(text="Made by hzh.")

            await ctx.edit(embed=embTdone)

            try: 
                await send_final(ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
            except HTTPError as e:
                errmsg = "HTTPError while uploading file to Google Drive, if problem reoccurs storage may be full."
                await errorHandling(ctx, errmsg, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

        else:
            await ctx.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Change(bot))