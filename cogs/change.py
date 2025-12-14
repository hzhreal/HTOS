import aiofiles.ospath
import discord
import asyncio
import os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, SHARED_GD_LINK_DESC, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    ICON0_FORMAT, ICON0_MAXSIZE, ICON0_NAME, COMMAND_COOLDOWN,
    logger
)
from utils.embeds import (
    embpng, embTitleChange, embTitleErr, embpng1, embpng2, embpngs, embPdone,
    embTitleChange1, embTitleSuccess, embTdone
)
from utils.workspace import init_workspace, make_workspace, cleanup, cleanup_simple
from utils.extras import pngprocess
from utils.helpers import DiscordContext, psusername, upload2, error_handling, send_final, task_handler
from utils.orbis import sfo_ctx_patch_parameters, SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global

class Change(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    change_group = discord.SlashCommandGroup("change")

    @change_group.command(description="Changes the picture of your save, this is just cosmetic.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def picture(
              self, 
              ctx: discord.ApplicationContext, 
              picture: discord.Attachment, 
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:

        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = init_workspace()
        workspace_folders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await make_workspace(ctx, workspace_folders, ctx.channel_id)
        except (WorkspaceError, discord.HTTPException): return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mount_paths = []
        pngfile = os.path.join(newPNG_PATH, ICON0_NAME)

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=embpng)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)

            # png handling
            await picture.save(pngfile)
            pngprocess(pngfile, ICON0_FORMAT)
            png_size = await aiofiles.ospath.getsize(pngfile)
            if png_size > ICON0_MAXSIZE:
                raise FileError(f"Image turned out to be too big: {png_size}/{ICON0_MAXSIZE}!")
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await error_handling(msg, err, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
            await error_handling(msg, e, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
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

                    emb = embpng1.copy()
                    emb.description = emb.description = emb.description = emb.description.format(savefile.basename, j, batch.savecount, i, batches)
                    task = [savefile.dump]
                    await task_handler(d_ctx, task, [emb])

                    emb = embpng2.copy()
                    emb.description = emb.description = emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        lambda: C1ftp.swap_png(batch.location_to_scesys),
                        savefile.resign
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    emb = embpngs.copy()
                    emb.description = emb.description.format(savefile.basename, j, batch.savecount, i, batches)
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
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await error_handling(msg, BASE_ERROR_MSG, workspace_folders, batch.entry, mount_paths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            emb = embPdone.copy()
            emb.description = emb.description.format(printed=batch.printed, id=playstation_id or user_id, i=i, batches=batches)
            try:
                await msg.edit(embed=embPdone)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                if isinstance(e, discord.HTTPException):
                    e = BASE_ERROR_MSG
                await error_handling(msg, e, workspace_folders, batch.entry, mount_paths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
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

    @change_group.command(description="Change the titles of your save.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def title(
              self, 
              ctx: discord.ApplicationContext, 
              maintitle: Option(str, description="For example Grand Theft Auto V.", default=""), # type: ignore
              subtitle: Option(str, description="For example Franklin and Lamar (1.6%).", default=""), # type: ignore
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:

        if maintitle == "" and subtitle == "":
            await ctx.respond(embed=embTitleErr)
            return
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
            msg = await ctx.edit(embed=embTitleChange)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await error_handling(msg, err, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError, TaskCancelledError) as e:
            await error_handling(msg, e, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
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

                    emb = embTitleChange1.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
                    tasks = [
                        savefile.dump,
                        lambda: savefile.download_sys_elements([savefile.ElementChoice.SFO])    
                    ]
                    await task_handler(d_ctx, tasks, [emb])

                    sfo_ctx_patch_parameters(savefile.sfo_ctx, MAINTITLE=maintitle, SUBTITLE=subtitle)

                    task = [savefile.resign]
                    await task_handler(d_ctx, task, [])

                    emb = embTitleSuccess.copy()
                    emb.description = emb.description.format(savename=savefile.basename, j=j, savecount=batch.savecount, i=i, batches=batches)
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
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await error_handling(msg, BASE_ERROR_MSG, workspace_folders, batch.entry, mount_paths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            emb = embTdone.copy()
            emb.description = emb.description.format(printed=batch.printed, id=playstation_id or user_id, i=i, batches=batches)
            try:
                await msg.edit(embed=emb)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
                if isinstance(e, discord.HTTPException):
                    e = BASE_ERROR_MSG
                await error_handling(msg, e, workspace_folders, batch.entry, mount_paths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
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
    bot.add_cog(Change(bot))
