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
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    embDecrypt1
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple
from utils.helpers import DiscordContext, upload2, errorHandling, send_final
from utils.orbis import SaveBatch, SaveFile
from utils.namespaces import Crypto
from utils.exceptions import FileError, OrbisError, WorkspaceError
from utils.instance_lock import INSTANCE_LOCK_global

class Decrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @discord.slash_command(description="Decrypt a savefile and download the contents.")
    async def decrypt(
              self, 
              ctx: discord.ApplicationContext, 
              include_sce_sys: Option(bool, description="Choose if you want to include the 'sce_sys' folder."), # type: ignore
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
            await ctx.respond(embed=embDecrypt1)
            msg = await ctx.edit(embed=embDecrypt1)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            shared_gd_folderid = await GDapi.parse_sharedfolder_link(shared_gd_link)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (TimeoutError, GDapiError, FileError, OrbisError) as e:
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
        batch = SaveBatch(C1ftp, C1socket, "", [], mountPaths, "")
        savefile = SaveFile("", batch)

        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
                destination_directory_outer = os.path.join(newDOWNLOAD_DECRYPTED, batch.rand_str) 
                await aiofiles.os.mkdir(destination_directory_outer)
            except OSError as e:
                await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()
                    destination_directory = os.path.join(destination_directory_outer, f"dec_{savefile.basename}")
                    await aiofiles.os.mkdir(destination_directory)

                    emb11 = discord.Embed(
                        title="Decryption process: Initializing",
                        description=f"Mounting {savefile.basename} (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    emb11.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb11)
            
                    await savefile.dump()

                    emb_dl = discord.Embed(
                        title="Decryption process: Downloading",
                        description=f"{savefile.basename} mounted (save {j}/{batch.savecount}, batch {i}/{batches}), downloading decrypted savefile...",
                        colour=Color.DEFAULT.value
                    ) 
                    emb_dl.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb_dl)

                    await C1ftp.download_folder(batch.mount_location, destination_directory, not include_sce_sys)

                    await savefile.download_sys_elements([savefile.ElementChoice.SFO])

                    await aiofiles.os.rename(destination_directory, destination_directory + f"_{savefile.title_id}")
                    destination_directory += f"_{savefile.title_id}"
                    await extra_decrypt(d_ctx, Crypto, savefile.title_id, destination_directory, savefile.basename)

                    emb13 = discord.Embed(
                        title="Decryption process: Successful",
                        description=f"Downloaded the decrypted save of **{savefile.basename}** (save {j}/{batch.savecount}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    emb13.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb13)
                    j += 1

                except (SocketError, FTPError, OrbisError, CryptoError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            embDdone = discord.Embed(
                title="Decryption process: Successful",
                description=f"**{batch.printed}** has been decrypted (batch {i}/{batches}).",
                colour=Color.DEFAULT.value
            )
            embDdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embDdone)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            if batches == 1 and len(batch.savenames) == 1:
                zipname = os.path.basename(destination_directory) + f"_{batch.rand_str}" + ZIPOUT_NAME[1]
            else:
                zipname = "Decrypted-Saves" + f"_{batch.rand_str}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, destination_directory_outer, shared_gd_folderid)
            except (GDapiError, discord.HTTPException) as e:
                await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return
            
            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Decrypt(bot))