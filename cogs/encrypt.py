import discord
import asyncio
import os
import aiofiles.os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from data.crypto import CryptoError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, SCE_SYS_CONTENTS, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    emb6, emb14
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames
from utils.helpers import psusername, upload2, errorHandling, send_final
from utils.orbis import obtainCUSA, parse_pfs_header, OrbisError
from utils.exceptions import PSNIDError, FileError
from utils.helpers import DiscordContext, replaceDecrypted

class Encrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Swap the decrypted savefile from the encrypted ones you upload.")
    async def encrypt(
              self, 
              ctx: discord.ApplicationContext, 
              upload_individually: Option(bool, description="Choose if you want to upload the decrypted files one by one, or the ones you want at once."), # type: ignore
              include_sce_sys: Option(bool, description="Choose if you want to upload the contents of the 'sce_sys' folder."), # type: ignore
              playstation_id: Option(str, description=PS_ID_DESC, default="") # type: ignore
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

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            msg = await ctx.edit(embed=emb14)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return

        savenames = await obtain_savenames(newUPLOAD_ENCRYPTED)
        full_completed = []

        if len(uploaded_file_paths) >= 2:
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)
                try:
                    pfs_path = os.path.join(newUPLOAD_ENCRYPTED, save)
                    pfs_header = await parse_pfs_header(pfs_path)
                    await aiofiles.os.rename(pfs_path, os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(pfs_path + ".bin", os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))

                    embmo = discord.Embed(
                        title="Encryption & Resigning process: Initializing",
                        description=f"Mounting {save}.",
                        colour=Color.DEFAULT.value
                    )
                    embmo.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embmo)

                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                
                    files = await C1ftp.ftpListContents(mount_location_new)

                    if len(files) == 0: raise FileError("Could not list any decrypted saves!")
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparamonly_grab(location_to_scesys)
                    title_id = await obtainCUSA(newPARAM_PATH)
 
                    completed = await replaceDecrypted(d_ctx, C1ftp, files, title_id, mount_location_new, upload_individually, newUPLOAD_DECRYPTED, save, pfs_header["size"])

                    if include_sce_sys:
                        if len(await aiofiles.os.listdir(newUPLOAD_DECRYPTED)) > 0:
                            shutil.rmtree(newUPLOAD_DECRYPTED)
                            await aiofiles.os.mkdir(newUPLOAD_DECRYPTED)
                            
                        embSceSys = discord.Embed(
                            title=f"Upload: sce_sys contents\n{save}",
                            description="Please attach the sce_sys files you want to upload.",
                            colour=Color.DEFAULT.value
                        )
                        embSceSys.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                        await msg.edit(embed=embSceSys)
                        uploaded_file_paths_sys = await upload2(d_ctx, newUPLOAD_DECRYPTED, max_files=len(SCE_SYS_CONTENTS), sys_files=True, ps_save_pair_upload=False, ignore_filename_check=False, savesize=pfs_header["size"])

                        if len(uploaded_file_paths_sys) <= len(SCE_SYS_CONTENTS) and len(uploaded_file_paths_sys) >= 1:
                            await C1ftp.upload_scesysContents(msg, uploaded_file_paths_sys, location_to_scesys)
                        
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparam(location_to_scesys, user_id)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    if len(completed) == 1: completed = "".join(completed)
                    else: completed = ", ".join(completed)
                    full_completed.append(completed)

                    embmidComplete = discord.Embed(
                        title="Encrypting & Resigning Process: Successful",
                        description=f"Resigned **{completed}** with title id **{title_id}** to **{playstation_id or user_id}**.",
                        colour=Color.DEFAULT.value
                    )
                    embmidComplete.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                    await msg.edit(embed=embmidComplete)
                except HTTPError as e:
                    err = GDapi.getErrStr_HTTPERROR(e)
                    await errorHandling(msg, err, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    return
                except (SocketError, FTPError, OrbisError, FileError, CryptoError, GDapiError, OSError, TimeoutError) as e:
                    status = "expected"
                    if isinstance(e, TimeoutError):
                        pass # we dont want TimeoutError in the OSError check because its a subclass
                    elif isinstance(e, OSError) and e.errno in CON_FAIL: 
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return
                
            if len(full_completed) == 1: full_completed = "".join(full_completed)
            else: full_completed = ", ".join(full_completed)

            embComplete = discord.Embed(
                title="Encrypting & Resigning Process: Successful: Successful",
                description=f"Resigned **{full_completed}** to **{playstation_id or user_id}**.",
                colour=Color.DEFAULT.value
            )
            embComplete.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            await msg.edit(embed=embComplete)

            try: 
                await send_final(d_ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
            except GDapiError as e:
                await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)
        else:
            await msg.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Encrypt(bot))