import discord
import asyncio
import os
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from data.crypto.exceptions import CryptoError
from data.crypto.helpers import extra_decrypt
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, COMMAND_COOLDOWN,
    logger
)
from utils.embeds import (
    embDecrypt1, emb11, emb_dl, emb13, embDdone
)
from utils.workspace import init_workspace, make_workspace, cleanup, cleanup_simple
from utils.helpers import DiscordContext, upload2, error_handling, send_final, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class Decrypt(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Decrypt a savefile and download the contents.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def decrypt(
              self,
              ctx: discord.ApplicationContext,
              include_sce_sys: Option(bool, description=(
                  "Choose if you want to include the 'sce_sys' folder."
              ), default=False),
              secondlayer_choice: Option(bool, description=(
                  "Apply or do not apply second layer implementation for all saves applicable."
              ), default=""),
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

        try:
            await ctx.respond(embed=embDecrypt1)
            msg = await ctx.edit(embed=embDecrypt1)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await error_handling(msg, err, workspace_folders, None, None, None)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
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
        batch = SaveBatch(C1ftp, C1socket, "", [], mount_paths, "")
        savefile = SaveFile("", batch)

        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
                destination_directory_outer = os.path.join(newDOWNLOAD_DECRYPTED, batch.rand_str) 
                await aiofiles.os.mkdir(destination_directory_outer)
            except OSError as e:
                await error_handling(msg, BASE_ERROR_MSG, workspace_folders, None, mount_paths, C1ftp)
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

                    emb = emb11.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    task = [savefile.dump]
                    await task_handler(d_ctx, task, [emb])

                    emb = emb_dl.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        lambda: C1ftp.download_folder(batch.mount_location, destination_directory, not include_sce_sys),
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO])
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    await aiofiles.os.rename(destination_directory, destination_directory + f"_{savefile.title_id}")
                    destination_directory += f"_{savefile.title_id}"
                    choice = secondlayer_choice if secondlayer_choice != "" else None
                    await extra_decrypt(d_ctx, savefile.title_id, destination_directory, savefile.basename, choice)

                    emb = emb13.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    await msg.edit(embed=emb)
                    j += 1
                except (SocketError, FTPError, OrbisError, CryptoError, OSError, TaskCancelledError) as e:
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

            emb = embDdone.copy()
            emb.description = emb.description.format(printed=batch.printed, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.info(f"Error while editing msg: {e}", exc_info=True)

            if batches == 1 and len(batch.savenames) == 1:
                zipname = os.path.basename(destination_directory) + f"_{batch.rand_str}" + ZIPOUT_NAME[1]
            else:
                zipname = "Decrypted-Saves" + f"_{batch.rand_str}" + ZIPOUT_NAME[1]

            try:
                await send_final(d_ctx, zipname, destination_directory_outer, shared_gd_folderid)
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
    bot.add_cog(Decrypt(bot))
