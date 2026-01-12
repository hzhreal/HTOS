import discord
import asyncio
import shutil
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, COMMAND_COOLDOWN,
    SPECIAL_REREGION_TITLEIDS,
    logger
)
from utils.embeds import (
    emb21, emb20, embkstone1, embkstone2, embrrp, embrrps, embrrdone
)
from utils.workspace import init_workspace, make_workspace, cleanup, cleanup_simple
from utils.helpers import DiscordContext, psusername, upload2, error_handling, send_final, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, WorkspaceError, OrbisError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class ReRegion(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Change the region of a save (Must be from the same game).")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def reregion(
              self,
              ctx: discord.ApplicationContext,
              playstation_id: Option(str, description=PS_ID_DESC, default=""),
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="")
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

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=emb21)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = (await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=2, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False))[0]
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

        batch = SaveBatch(C1ftp, C1socket, user_id, uploaded_file_paths, mount_paths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch, True)
        try:
            await batch.construct()
            savefile.path = uploaded_file_paths[0].removesuffix(".bin")
            await savefile.construct()

            emb = embkstone1.copy()
            emb.description = emb.description.format(savename=savefile.basename)
            tasks = [
                savefile.dump,
                lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO, savefile.ElementChoice.KEYSTONE])
            ]
            await task_handler(d_ctx, tasks, [emb])

            target_titleid = savefile.title_id

            emb = embkstone2.copy()
            emb.description = emb.description.format(target_titleid=target_titleid)
            await msg.edit(embed=emb)

            shutil.rmtree(newUPLOAD_ENCRYPTED)
            await aiofiles.os.mkdir(newUPLOAD_ENCRYPTED)

            await C1ftp.delete_list(PS_UPLOADDIR, [savefile.realSave, savefile.realSave + ".bin"])
        except (SocketError, FTPError, OrbisError, OSError, TaskCancelledError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
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

        try:
            await msg.edit(embed=emb20)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await error_handling(msg, err, workspace_folders, None, mount_paths, C1ftp)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
            await error_handling(msg, e, workspace_folders, None, mount_paths, C1ftp)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await error_handling(msg, BASE_ERROR_MSG, workspace_folders, None, mount_paths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        special_reregion = target_titleid in SPECIAL_REREGION_TITLEIDS

        batches = len(uploaded_file_paths)

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

            extra_msg = ""
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()
                    savefile.title_id = target_titleid
                    savefile.downloaded_sys_elements.add(savefile.ElementChoice.KEYSTONE)

                    emb = embrrp.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        savefile.dump,
                        savefile.resign
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    emb = embrrps.copy()
                    emb.description = emb.description.format(savename=savefile.basename, id=playstation_id or user_id, target_titleid=target_titleid, j=j, savecount=batch.savecount, i=i, batches=batches)
                    await msg.edit(embed=emb)
                    j += 1
                except (SocketError, FTPError, OrbisError, OSError, TaskCancelledError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL: 
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

            emb = embrrdone.copy()
            emb.description = emb.description.format(printed=batch.printed, id=playstation_id or user_id, target_titleid=target_titleid, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.info(f"Error while editing msg: {e}", exc_info=True)

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            if special_reregion and not extra_msg and j > 2:
                extra_msg = (
                    "Make sure to remove the random string after and including '_' when you are going to copy that file to the console. "
                    "May be required if you re-regioned more than 1 save at once."
                )

            try:
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid, extra_msg)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                if isinstance(e, discord.HTTPException):
                    e = BASE_ERROR_MSG
                await error_handling(msg, e, workspace_folders, uploaded_file_paths, mount_paths, C1ftp)
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
    bot.add_cog(ReRegion(bot))
