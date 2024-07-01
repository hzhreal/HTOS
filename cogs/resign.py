import discord
import asyncio
import os
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    embEncrypted1, emb6
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, send_final
from utils.orbis import OrbisError
from utils.exceptions import PSNIDError, FileError

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
        
        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            msg = await ctx.edit(embed=embEncrypted1)
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

        if len(uploaded_file_paths) >= 2:
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)
                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))

                    emb4 = discord.Embed(
                        title="Resigning process: Encrypted",
                        description=f"Your save (**{save}**) is being resigned, please wait...",
                        colour=Color.DEFAULT.value
                    )
                    emb4.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb4)

                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparam(location_to_scesys, user_id)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    emb5 = discord.Embed(
                        title="Resigning process (Encrypted): Successful",
                        description=f"**{save}** resigned to **{playstation_id or user_id}**.",
                        colour=Color.DEFAULT.value
                    )
                    emb5.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb5)

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL: 
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
                
            if len(savenames) == 1:
                finishedFiles = "".join(savenames)
            else: finishedFiles = ", ".join(savenames)
            
            embRdone = discord.Embed(
                title="Resigning process (Encrypted): Successful",
                description=f"**{finishedFiles}** resigned to **{playstation_id or user_id}**.",
                colour=Color.DEFAULT.value)
            embRdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embRdone)

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
    bot.add_cog(Resign(bot))