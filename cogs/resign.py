import discord
import asyncio
import os
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC,
    logger, Color,
    embEncrypted1, embhttp, emb6
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames
from utils.helpers import psusername, upload2, errorHandling, send_final
from utils.orbis import OrbisError
from utils.exceptions import PSNIDError

class Resign(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @discord.slash_command(description="Resign encrypted savefiles (the usable ones you put in the console).")
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
            await ctx.edit(embed=embEncrypted1)
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
                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    emb4 = discord.Embed(title="Resigning process: Encrypted",
                                description=f"Your save (**{save}**) is being resigned, please wait...",
                                colour=Color.DEFAULT.value)
                    emb4.set_footer(text="Made by hzh.")

                    await ctx.edit(embed=emb4)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparam(location_to_scesys, user_id)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    emb5 = discord.Embed(title="Resigning process (Encrypted): Successful",
                                description=f"**{save}** resigned to **{playstation_id or user_id}**.",
                                colour=Color.DEFAULT.value)
                    emb5.set_footer(text="Made by hzh.")

                    await ctx.edit(embed=emb5)

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
            
            embRdone = discord.Embed(title="Resigning process (Encrypted): Successful",
                                description=f"**{finishedFiles}** resigned to **{playstation_id or user_id}**.",
                                colour=Color.DEFAULT.value)
            embRdone.set_footer(text="Made by hzh.")
            
            await ctx.edit(embed=embRdone)

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
    bot.add_cog(Resign(bot))