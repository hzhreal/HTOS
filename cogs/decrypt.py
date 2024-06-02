import discord
import asyncio
import os
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from data.crypto import extra_decrypt, CryptoError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, CON_FAIL, CON_FAIL_MSG,
    logger, Color,
    emb6, embDecrypt1
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames
from utils.helpers import upload2, errorHandling, send_final
from utils.orbis import obtainCUSA, OrbisError
from utils.namespaces import Crypto
from utils.exceptions import FileError

class Decrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @discord.slash_command(description="Decrypt a savefile and download the contents.")
    async def decrypt(
              self, 
              ctx: discord.ApplicationContext, 
              include_sce_sys: Option(bool, description="Choose if you want to include the 'sce_sys' folder.") # type: ignore
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

        await ctx.respond(embed=embDecrypt1)
        try:
            uploaded_file_paths = await upload2(ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(ctx, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (TimeoutError, GDapiError, FileError, OrbisError) as e:
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
                destination_directory = os.path.join(newDOWNLOAD_DECRYPTED, f"dec_{save}")
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)

                emb11 = discord.Embed(title="Decrypt process: Initializing",
                        description=f"Mounting {save}.",
                        colour=Color.DEFAULT.value)
                emb11.set_footer(text="Made by hzh.")
                
                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    await aiofiles.os.mkdir(destination_directory)
                    await ctx.edit(embed=emb11)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)

                    emb_dl = discord.Embed(title="Decrypt process: Downloading",
                      description=f"{save} mounted, downloading decrypted savefile.",
                      colour=Color.DEFAULT.value) 
                    emb_dl.set_footer(text="Made by hzh.")
                    await ctx.edit(embed=emb_dl)

                    if include_sce_sys:
                        await C1ftp.ftp_download_folder(mount_location_new, destination_directory, False)
                    else:
                        await C1ftp.ftp_download_folder(mount_location_new, destination_directory, True)
                    
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparamonly_grab(location_to_scesys)
                    title_id_grab = await obtainCUSA(newPARAM_PATH)
                    await aiofiles.os.rename(destination_directory, destination_directory + f"_{title_id_grab}")
                    destination_directory = destination_directory + f"_{title_id_grab}"

                    emb13 = discord.Embed(title="Decrypt process: Successful",
                                description=f"Downloaded the decrypted save of **{save}** from **{title_id_grab}**.",
                                colour=Color.DEFAULT.value)
                    emb13.set_footer(text="Made by hzh.")
                    
                    await extra_decrypt(ctx, Crypto, title_id_grab, destination_directory, save)

                    await ctx.edit(embed=emb13)

                except (SocketError, FTPError, OrbisError, CryptoError, OSError) as e:
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
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

            embDdone = discord.Embed(title="Decryption process: Successful",
                                description=f"**{finishedFiles}** has been decrypted.",
                                colour=Color.DEFAULT.value)
            embDdone.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embDdone)

            if len(await aiofiles.os.listdir(newDOWNLOAD_DECRYPTED)) == 1:
                zip_name = os.listdir(newDOWNLOAD_DECRYPTED)
                zip_name = "".join(zip_name)
                zip_name += ".zip"
            else:
                zip_name = "Decrypted-Saves.zip"

            try: 
                await send_final(ctx, zip_name, newDOWNLOAD_DECRYPTED)
            except GDapiError as e:
                await errorHandling(ctx, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return
            
            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

        else:
            await ctx.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Decrypt(bot))