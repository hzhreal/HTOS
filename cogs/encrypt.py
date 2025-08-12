import asyncio.selector_events
import discord
import asyncio
import aiofiles.os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, C1socket, FTPError, SocketError
from google_drive import gdapi, GDapiError
from data.crypto import CryptoError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, COMMAND_COOLDOWN,
    SCE_SYS_CONTENTS, PS_ID_DESC, IGNORE_SECONDLAYER_DESC, CON_FAIL, CON_FAIL_MSG, SHARED_GD_LINK_DESC,
    logger, Color, Embed_t,
    emb14, cancel_notify_emb
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple
from utils.extras import completed_print
from utils.helpers import psusername, upload2, errorHandling, send_final, UploadOpt, UploadGoogleDriveChoice, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.helpers import DiscordContext, replaceDecrypted
from utils.instance_lock import INSTANCE_LOCK_global

class Encrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Swap the decrypted savefile from the encrypted ones you upload.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def encrypt(
              self, 
              ctx: discord.ApplicationContext, 
              upload_individually: Option(bool, description="Choose if you want to upload the decrypted files one by one, or the ones you want at once."), # type: ignore
              include_sce_sys: Option(bool, description="Choose if you want to upload the contents of the 'sce_sys' folder."), # type: ignore
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default=""), # type: ignore
              ignore_secondlayer_checks: Option(bool, description=IGNORE_SECONDLAYER_DESC, default=False) # type: ignore
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
        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, True)

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=emb14)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False, opt=opt)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
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
        batch = SaveBatch(C1ftp, C1socket, user_id, [], mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)
        
        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError as e:
                await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    pfs_size = await aiofiles.os.path.getsize(savepath) # check has already been done
                    await savefile.construct()

                    embmo = discord.Embed(
                        title="Encryption process: Initializing",
                        description=f"Mounting **{savefile.basename}**, (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...\nSend 'EXIT' to cancel.",
                        colour=Color.DEFAULT.value
                    )
                    embmo.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    tasks = [
                        savefile.dump,
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO])
                    ]
                    await task_handler(d_ctx, tasks, [embmo])
                
                    files = await C1ftp.list_files(batch.mount_location)
                    if len(files) == 0: 
                        raise FileError("Could not list any decrypted saves!")

                    completed = await replaceDecrypted(
                        d_ctx, C1ftp, files, savefile.title_id, 
                        batch.mount_location, upload_individually, 
                        newUPLOAD_DECRYPTED, savefile.basename, pfs_size, ignore_secondlayer_checks
                    )

                    if include_sce_sys:
                        shutil.rmtree(newUPLOAD_DECRYPTED)
                        await aiofiles.os.mkdir(newUPLOAD_DECRYPTED)
                            
                        embSceSys = discord.Embed(
                            title=f"Upload: sce_sys contents\n{savefile.basename}",
                            description="Please attach the sce_sys files you want to upload. Or type 'EXIT' to cancel command.",
                            colour=Color.DEFAULT.value
                        )
                        embSceSys.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                        await msg.edit(embed=embSceSys)

                        uploaded_file_paths_sys = (await upload2(d_ctx, newUPLOAD_DECRYPTED, max_files=len(SCE_SYS_CONTENTS), sys_files=True, ps_save_pair_upload=False, ignore_filename_check=False, savesize=pfs_size))[0]
                        await C1ftp.upload_scesysContents(msg, uploaded_file_paths_sys, batch.location_to_scesys)

                    tasks = [
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO]),
                        savefile.resign
                    ]
                    await task_handler(d_ctx, tasks, [cancel_notify_emb])

                    dec_print = completed_print(completed)

                    embmidComplete = discord.Embed(
                        title="Encryption Processs: Successful",
                        description=f"Encrypted **{dec_print}** into **{savefile.basename}** for **{playstation_id or user_id}** (save {j}/{batch.savecount}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    embmidComplete.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embmidComplete)
                    j += 1
                except HTTPError as e:
                    err = gdapi.getErrStr_HTTPERROR(e)
                    await errorHandling(msg, err, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (expected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except (SocketError, FTPError, OrbisError, FileError, CryptoError, GDapiError, OSError, TimeoutError, TaskCancelledError) as e:
                    status = "expected"
                    if isinstance(e, TimeoutError):
                        pass # we dont want TimeoutError in the OSError check because its a subclass
                    elif isinstance(e, OSError) and e.errno in CON_FAIL:
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

            embComplete = discord.Embed(
                title="Encryption process: Successful",
                description=(
                    f"Encrypted files into **{batch.printed}** for **{playstation_id or user_id}** (batch {i}/{batches}).\n"
                    "Uploading file...\n"
                    "If file is being uploaded to Google Drive, you can send 'EXIT' to cancel."
                ),
                colour=Color.DEFAULT.value
            )
            embComplete.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embComplete)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

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

            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Encrypt(bot))