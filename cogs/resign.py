import discord
import asyncio
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, ZIPOUT_NAME, COMMAND_COOLDOWN,
    logger
)
from utils.embeds import (
    embEncrypted1, embres, embress, embRbdone
)
from utils.workspace import init_workspace, make_workspace, cleanup, cleanup_simple
from utils.helpers import DiscordContext, psusername, upload2, error_handling, send_final, task_handler
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class Resign(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Resign encrypted savefiles (the usable ones you put in the console).")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def resign(
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
            msg = await ctx.edit(embed=embEncrypted1)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
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
                    await savefile.construct()

                    emb = embres.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        savefile.dump,
                        savefile.resign
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    emb = embress.copy()
                    emb.description = emb.description.format(savename=savefile.basename, id=playstation_id or user_id, j=j, savecount=batch.savecount, i=i, batches=batches)
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

            emb = embRbdone.copy()
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
    bot.add_cog(Resign(bot))
