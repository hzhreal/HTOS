import discord
import aiofiles.os
import asyncio
import os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network.socket_functions import C1socket
from network.ftp_functions import FTPps
from network.exceptions import SocketError, FTPError
from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from data.crypto.helpers import extra_import
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MOUNT_LOCATION, PARAM_NAME, COMMAND_COOLDOWN, SAVESIZE_MB_MIN, SAVESIZE_MB_MAX, SCE_SYS_NAME,
    SAVEBLOCKS_MAX, SAVEBLOCKS_MIN, SCE_SYS_CONTENTS, BASE_ERROR_MSG, PS_ID_DESC, ZIPOUT_NAME, SHARED_GD_LINK_DESC,
    IGNORE_SECONDLAYER_DESC, MAX_FILES, CON_FAIL_MSG, CON_FAIL,
    logger
)
from utils.embeds import (
    embSceSys, embgs, embc, embCRdone
)
from utils.workspace import make_workspace, init_workspace, cleanup
from utils.helpers import (
    DiscordContext, error_handling, upload2, send_final,
    psusername, upload2_special, task_handler, embed_edit, embed_construct
)
from utils.orbis import (
    sfo_ctx_patch_parameters, obtainCUSA,
    validate_savedirname, validate_savedirname_path,
    sfo_ctx_create, sfo_ctx_write, sys_files_validator, fix_pfs_auth_code_info
)
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.instance_lock import INSTANCE_LOCK_global
from utils.conversions import saveblocks_to_bytes, mb_to_saveblocks

SAVEBLOCKS_DESC = f"The value you put in will determine savesize (blocks * 32768)."
SAVESIZE_MB_DESC = "The value you put in will determine savesize (in MB)."

class CreateSave(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    DISC_UPL_SPLITVALUE = "SLASH"

    @discord.slash_command(description="Create savedata from scratch.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def createsave(
              self,
              ctx: discord.ApplicationContext,
              savename: Option(str, description="The name of the save."),
              saveblocks: Option(int, description=SAVEBLOCKS_DESC, min_value=SAVEBLOCKS_MIN, max_value=SAVEBLOCKS_MAX, default=0),
              savesize_mb: Option(int, description=SAVESIZE_MB_DESC, min_value=SAVESIZE_MB_MIN, max_value=SAVESIZE_MB_MAX, default=0),
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
        scesys_local = os.path.join(newUPLOAD_DECRYPTED, SCE_SYS_NAME)
        rand_str = os.path.basename(newUPLOAD_DECRYPTED)

        # saveblocks takes priority
        if saveblocks:
            savesize = saveblocks_to_bytes(saveblocks)
        elif savesize_mb:
            saveblocks = mb_to_saveblocks(savesize_mb)
            savesize = saveblocks_to_bytes(saveblocks)
        else:
            e = "You need to add the `saveblocks` or `savesize_mb` argument!"
            await error_handling(ctx, e, workspace_folders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        emb1 = embed_construct(
            embSceSys, title_kwargs=dict(
                savename=savename
            )
        )
        emb2 = embed_construct(
            embgs,
            title_kwargs=dict(
                savename=savename
            ),
            description_kwargs=dict(
                splitvalue=self.DISC_UPL_SPLITVALUE
            )
        )

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)

            # value checks
            validate_savedirname(savename)
            # length checks
            validate_savedirname_path(savename)

            msg = await ctx.edit(embed=emb1)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both

            # handle sce_sys first
            await aiofiles.os.mkdir(scesys_local)
            await asyncio.sleep(0.5)
            uploaded_file_paths_sys = (await upload2(
                d_ctx, scesys_local,
                max_files=len(SCE_SYS_CONTENTS), sys_files=True, ps_save_pair_upload=False, ignore_filename_check=False)
            )[0]
            sys_files_validator(uploaded_file_paths_sys)

            # next, other files (gamesaves)
            await msg.edit(embed=emb2)
            _ = await upload2_special(d_ctx, newUPLOAD_DECRYPTED, MAX_FILES, self.DISC_UPL_SPLITVALUE, savesize)
        except HTTPError as e:
            err = gdapi.get_err_str_HTTPERROR(e)
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

        uploaded_file_paths = []
        sfo_path = os.path.join(scesys_local, PARAM_NAME)
        try:
            sfo_ctx = await sfo_ctx_create(sfo_path)
            sfo_ctx_patch_parameters(sfo_ctx, ACCOUNT_ID=user_id, SAVEDATA_DIRECTORY=savename, SAVEDATA_BLOCKS=saveblocks)
            title_id = obtainCUSA(sfo_ctx)
            await sfo_ctx_write(sfo_ctx, sfo_path)

            if not ignore_secondlayer_checks:
                await extra_import(title_id, newUPLOAD_DECRYPTED, savename)

            await embed_edit(
                msg, embc,
                description_kwargs=dict(
                    savename=savename
                ), ignore_exc=True
            )

            temp_savename = savename + f"_{rand_str}"
            mount_location_new = MOUNT_LOCATION + "/" + rand_str
            location_to_scesys = mount_location_new + f"/{SCE_SYS_NAME}"

            task = [lambda: C1socket.socket_createsave(PS_UPLOADDIR, temp_savename, saveblocks)]
            await task_handler(d_ctx, task, [])
            uploaded_file_paths.extend([temp_savename, f"{savename}_{rand_str}.bin"])

            mount_paths.append(mount_location_new)
            tasks = [
                # now mount save and get ready to upload files to it
                lambda: C1ftp.make1(mount_location_new),
                lambda: C1ftp.make1(location_to_scesys),
                # dump, and begin uploading
                lambda: C1socket.socket_dump(mount_location_new, temp_savename),
                lambda: C1ftp.upload_scesys_contents(msg, uploaded_file_paths_sys, location_to_scesys),
            ]
            await task_handler(d_ctx, tasks, [])
            shutil.rmtree(scesys_local)

            tasks = [
                lambda: C1ftp.upload_folder(mount_location_new, newUPLOAD_DECRYPTED),
                lambda: C1socket.socket_update(mount_location_new, temp_savename)
            ]
            await task_handler(d_ctx, tasks, [])

            # make paths for save
            save_dirs = os.path.join(newDOWNLOAD_ENCRYPTED, "PS4", "SAVEDATA", user_id, title_id)
            await aiofiles.os.makedirs(save_dirs)

            # download save at real filename path
            savepath = os.path.join(save_dirs, savename)
            tasks = [
                lambda: C1ftp.download_file_streamed(PS_UPLOADDIR + "/" + temp_savename, savepath),
                lambda: C1ftp.download_file_streamed(PS_UPLOADDIR + "/" + temp_savename + ".bin", savepath + ".bin")
            ]
            await task_handler(d_ctx, tasks, [])
            await fix_pfs_auth_code_info(savepath)
        except (SocketError, FTPError, OSError, OrbisError, TaskCancelledError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            await error_handling(msg, e, workspace_folders, uploaded_file_paths, mount_paths, C1ftp)
            if status == "expected":
                logger.info(f"{e} - {ctx.user.name} - ({status})", exc_info=True)
            else:
                logger.exception(f"{e} - {ctx.user.name} - ({status})")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await error_handling(msg, BASE_ERROR_MSG, workspace_folders, uploaded_file_paths, mount_paths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        await embed_edit(
            msg, embCRdone,
            description_kwargs=dict(
                savename=savename, id=playstation_id or user_id
            )
        )

        zipname = ZIPOUT_NAME[0] + f"_{rand_str}_1" + ZIPOUT_NAME[1]

        try:
            await send_final(d_ctx, zipname, newDOWNLOAD_ENCRYPTED, shared_gd_folderid)
        except (GDapiError, discord.HTTPException, TaskCancelledError, FileError, TimeoutError) as e:
            if isinstance(e, discord.HTTPException):
                e = BASE_ERROR_MSG
            await error_handling(msg, e, workspace_folders, uploaded_file_paths, mount_paths, C1ftp)
            logger.info(f"{e} - {ctx.user.name} - (expected)", exc_info=True)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await error_handling(msg, BASE_ERROR_MSG, workspace_folders, uploaded_file_paths, mount_paths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        await cleanup(C1ftp, workspace_folders, uploaded_file_paths, mount_paths)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(CreateSave(bot))

