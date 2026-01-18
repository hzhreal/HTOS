import discord
import asyncio
import aiofiles.os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from data.crypto.exceptions import CryptoError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, COMMAND_COOLDOWN,
    SCE_SYS_CONTENTS, PS_ID_DESC, IGNORE_SECONDLAYER_DESC, CON_FAIL, CON_FAIL_MSG, SHARED_GD_LINK_DESC,
    logger
)
from utils.embeds import (
    emb14, cancel_notify_emb, embmo, embSceSys, embmidComplete, embencComplete
)
from utils.workspace import init_workspace, make_workspace, cleanup, cleanup_simple
from utils.extras import completed_print
from utils.helpers import psusername, upload2, error_handling, send_final, UploadOpt, UploadGoogleDriveChoice, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.helpers import DiscordContext, replace_decrypted
from utils.instance_lock import INSTANCE_LOCK_global

class Encrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Swap the decrypted savefile from the encrypted ones you upload.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def encrypt(
              self,
              ctx: discord.ApplicationContext,
              upload_individually: Option(bool, description=(
                  "Choose if you want to upload the decrypted files one by one, or the ones you want at once."
              )),
              include_sce_sys: Option(bool, description=(
                  "Choose if you want to upload the contents of the 'sce_sys' folder."
              ), default=False),
              playstation_id: Option(str, description=PS_ID_DESC, default=""),
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default=""),
              ignore_secondlayer_checks: Option(bool, description=IGNORE_SECONDLAYER_DESC, default=False)
            ) -> None:

        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = init_workspace()
        workspace_folders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED,
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await make_workspace(ctx, workspace_folders, ctx.channel_id)
        except (WorkspaceError, discord.HTTPException): return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mount_paths = []

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
            await error_handling(msg, err, workspace_folders, None, None, None)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
            await error_handling(msg, e, workspace_folders, None, None, None)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await error_handling(msg, BASE_ERROR_MSG, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        batches = len(uploaded_file_paths)
        batch = SaveBatch(C1ftp, C1socket, user_id, [], mount_paths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)

        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError as e:
                await error_handling(msg, BASE_ERROR_MSG, workspace_folders, None, mount_paths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    pfs_size = await aiofiles.os.path.getsize(savepath) # check has already been done
                    await savefile.construct()

                    emb = embmo.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        savefile.dump,
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO])
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    files = await C1ftp.list_files(batch.mount_location)
                    if len(files) == 0: 
                        raise FileError("Could not list any decrypted saves!")

                    completed = await replace_decrypted(
                        d_ctx, C1ftp, files, savefile.title_id,
                        batch.mount_location, upload_individually,
                        newUPLOAD_DECRYPTED, savefile.basename, pfs_size, ignore_secondlayer_checks
                    )

                    if include_sce_sys:
                        shutil.rmtree(newUPLOAD_DECRYPTED)
                        await aiofiles.os.mkdir(newUPLOAD_DECRYPTED)

                        emb = embSceSys.copy()
                        emb.title = emb.title.format(savename=savefile.basename)
                        await msg.edit(embed=emb)

                        uploaded_file_paths_sys = (await upload2(
                            d_ctx,
                            newUPLOAD_DECRYPTED,
                            max_files=len(SCE_SYS_CONTENTS),
                            sys_files=True,
                            ps_save_pair_upload=False,
                            ignore_filename_check=False,
                            savesize=pfs_size)
                        )[0]
                        await C1ftp.upload_scesysContents(msg, uploaded_file_paths_sys, batch.location_to_scesys)

                    tasks = [
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO]),
                        savefile.resign
                    ]
                    await task_handler(d_ctx, tasks, [cancel_notify_emb])

                    dec_print = completed_print(completed)

                    emb = embmidComplete.copy()
                    emb.description = emb.description.format(dec_print=dec_print, savename=savefile.basename, id=playstation_id or user_id, j=j, savecount=batch.savecount, i=i, batches=batches)
                    await msg.edit(embed=emb)
                    j += 1
                except HTTPError as e:
                    err = gdapi.getErrStr_HTTPERROR(e)
                    await error_handling(msg, err, workspace_folders, batch.entry, mount_paths, C1ftp)
                    logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
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
                    await error_handling(msg, e, workspace_folders, batch.entry, mount_paths, C1ftp)
                    if status == "expected":
                        logger.info(f"{e} - {ctx.user.name} - ({status})", exc_info=True)
                    else:
                        logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await error_handling(msg, BASE_ERROR_MSG, workspace_folders, batch.entry, mount_paths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            emb = embencComplete.copy()
            emb.description = emb.description.format(printed=batch.printed, id=playstation_id or user_id, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.info(f"Error while editing msg: {e}", exc_info=True)

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try:
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                if isinstance(e, discord.HTTPException):
                    e = BASE_ERROR_MSG
                await error_handling(msg, e, workspace_folders, batch.entry, mount_paths, C1ftp)
                logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return
            except Exception as e:
                await error_handling(msg, BASE_ERROR_MSG, workspace_folders, batch.entry, mount_paths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mount_paths)
            i += 1
        await cleanup_simple(workspace_folders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Encrypt(bot))
