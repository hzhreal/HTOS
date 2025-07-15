import discord
import aiofiles.os
import asyncio
import os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, C1socket, SocketError, FTPError
from google_drive import gdapi, GDapiError
from data.crypto.helpers import extra_import
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, MOUNT_LOCATION, PARAM_NAME, SAVESIZE_MAX, COMMAND_COOLDOWN,
    SAVEBLOCKS_MAX, SAVEBLOCKS_MIN, SCE_SYS_CONTENTS, BASE_ERROR_MSG, PS_ID_DESC, ZIPOUT_NAME, SHARED_GD_LINK_DESC,
    IGNORE_SECONDLAYER_DESC, RANDOMSTRING_LENGTH, MAX_FILES, CON_FAIL_MSG, CON_FAIL, MAX_FILENAME_LEN, MAX_PATH_LEN, CREATESAVE_ENC_CHECK_LIMIT,
    Color, Embed_t, logger
)
from utils.workspace import makeWorkspace, initWorkspace, cleanup
from utils.helpers import DiscordContext, errorHandling, upload2, send_final, psusername, upload2_special, task_handler
from utils.orbis import handleTitles, obtainCUSA, validate_savedirname, sfo_ctx_create, sfo_ctx_write, sys_files_validator
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError, TaskCancelledError
from utils.namespaces import Crypto
from utils.instance_lock import INSTANCE_LOCK_global
from utils.conversions import saveblocks_to_bytes, mb_to_saveblocks, bytes_to_mb

SAVEBLOCKS_DESC = f"The value you put in will determine savesize (blocks * 32768)."

SAVESIZE_MB_MIN = 3 # keep in mind minimum saveblocks
SAVESIZE_MB_MAX = bytes_to_mb(SAVESIZE_MAX)
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
              savename: Option(str, description="The name of the save."), # type: ignore
              saveblocks: Option(int, description=SAVEBLOCKS_DESC, min_value=SAVEBLOCKS_MIN, max_value=SAVEBLOCKS_MAX, default=0), # type: ignore
              savesize_mb: Option(int, description=SAVESIZE_MB_DESC, min_value=SAVESIZE_MB_MIN, max_value=SAVESIZE_MB_MAX, default=0), # type: ignore 
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
        scesys_local = os.path.join(newUPLOAD_DECRYPTED, "sce_sys")
        rand_str = os.path.basename(newUPLOAD_DECRYPTED)

        # saveblocks takes priority
        if saveblocks:
            savesize = saveblocks_to_bytes(saveblocks)
        elif savesize_mb:
            saveblocks = mb_to_saveblocks(savesize_mb)
            savesize = saveblocks_to_bytes(saveblocks)
        else:
            e = "You need to add the `saveblocks` or `savesize_mb` argument!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        embSceSys = discord.Embed(
            title=f"Upload: sce_sys contents\n{savename}",
            description="Please attach the sce_sys files you want to upload. Or type 'EXIT' to cancel command.",
            colour=Color.DEFAULT.value
        )
        embSceSys.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        embgs = discord.Embed(
            title=f"Upload: Gamesaves\n{savename}",
            description=(
                "Please attach the gamesaves files you want to upload.\n"
                "**FOLLOW THESE INSTRUCTIONS CAREFULLY**\n\n"
                f"For **discord uploads** rename the files according to the path they are going to have inside the savefile using the value '{self.DISC_UPL_SPLITVALUE}'. For example the file 'savedata' inside the data directory would be called 'data{self.DISC_UPL_SPLITVALUE}savedata'.\n\n"
                "For **google drive uploads** just create the directories on the drive and send the folder link from root, it will be recursively downloaded.\n\n"
                "*Or type 'EXIT' to cancel command.*"
            ),
            colour=Color.DEFAULT.value
        )
        embgs.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)

            # value checks
            if not validate_savedirname(savename):
                raise OrbisError("Invalid savename!")

            # length checks
            filename_bin = f"{savename}.bin_{'X' * RANDOMSTRING_LENGTH}"
            filename_bin_len = len(filename_bin)
            path_len = len(PS_UPLOADDIR + "/" + filename_bin + "/")

            if filename_bin_len > MAX_FILENAME_LEN:
                raise OrbisError(f"The length of the savename will exceed {MAX_FILENAME_LEN}!")
            elif path_len > MAX_PATH_LEN:
                raise OrbisError(f"The path the save creates will exceed {MAX_PATH_LEN}!")

            msg = await ctx.edit(embed=embSceSys)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both

            # handle sce_sys first
            await aiofiles.os.mkdir(scesys_local)
            await asyncio.sleep(0.5)
            uploaded_file_paths_sys = (await upload2(d_ctx, scesys_local, max_files=len(SCE_SYS_CONTENTS), sys_files=True, ps_save_pair_upload=False, ignore_filename_check=False))[0]
            sys_files_validator(uploaded_file_paths_sys)

            # next, other files (gamesaves)
            await msg.edit(embed=embgs)
            uploaded_file_paths_special = await upload2_special(d_ctx, newUPLOAD_DECRYPTED, MAX_FILES, self.DISC_UPL_SPLITVALUE, savesize)
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
        
        uploaded_file_paths = []
        sfo_path = os.path.join(scesys_local, PARAM_NAME)
        try:
            sfo_ctx = await sfo_ctx_create(sfo_path)
            handleTitles(sfo_ctx, user_id, SAVEDATA_DIRECTORY=savename, SAVEDATA_BLOCKS=saveblocks)
            title_id = obtainCUSA(sfo_ctx)
            await sfo_ctx_write(sfo_ctx, sfo_path)

            if len(uploaded_file_paths_special) <= CREATESAVE_ENC_CHECK_LIMIT and not ignore_secondlayer_checks: # dont want to create unnecessary overhead
                path_idx = len(newUPLOAD_DECRYPTED) + (newUPLOAD_DECRYPTED[-1] != os.path.sep)
                for gamesave in uploaded_file_paths_special:
                    displaysave = gamesave[path_idx:]
                    embsl = discord.Embed(
                        title=f"Gamesaves: Second layer\n{displaysave}",
                        description="Checking for supported second layer encryption/compression...",
                        colour=Color.DEFAULT.value
                    )
                    embsl.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embsl)
                    await asyncio.sleep(0.5)
                    await extra_import(Crypto, title_id, gamesave)

            embc = discord.Embed(
                title="Processing",
                description=f"Creating {savename}...",
                colour=Color.DEFAULT.value
            )
            embc.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embc)

            temp_savename = savename + f"_{rand_str}"
            mount_location_new = MOUNT_LOCATION + "/" + rand_str
            location_to_scesys = mount_location_new + "/" + "sce_sys"

            task = [lambda: C1socket.socket_createsave(PS_UPLOADDIR, temp_savename, saveblocks)]
            await task_handler(d_ctx, task, [])
            uploaded_file_paths.extend([temp_savename, f"{savename}_{rand_str}.bin"])
            
            # now mount save and get ready to upload files to it
            tasks = [lambda: C1ftp.make1(mount_location_new), lambda: C1ftp.make1(location_to_scesys)]
            await task_handler(d_ctx, tasks, [])
            mountPaths.append(mount_location_new)

            task = [lambda: C1socket.socket_dump(mount_location_new, temp_savename)]
            await task_handler(d_ctx, task, [])

            # upload now
            task = [lambda: C1ftp.upload_scesysContents(msg, uploaded_file_paths_sys, location_to_scesys)]
            await task_handler(d_ctx, task)
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
            ftp_ctx = await C1ftp.create_ctx()
            tasks = [
                lambda: C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename, os.path.join(save_dirs, savename)),
                lambda: C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename + ".bin", os.path.join(save_dirs, savename + ".bin"))
            ]
            await task_handler(d_ctx, tasks, [])
            await C1ftp.free_ctx(ftp_ctx)
        except (SocketError, FTPError, OSError, OrbisError, TaskCancelledError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - ({status})")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        
        embRdone = discord.Embed(
            title="Creation process: Successful",
            description=(
                f"**{savename}** created & resigned to **{playstation_id or user_id}**.\n"
                "Uploading file...\n"
                "If file is being uploaded to Google Drive, you can send 'EXIT' to cancel."
            ),
            colour=Color.DEFAULT.value
        )
        embRdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        try:
            await msg.edit(embed=embRdone)
        except discord.HTTPException as e:
            logger.exception(f"Error while editing msg: {e}")

        zipname = ZIPOUT_NAME[0] + f"_{rand_str}_1" + ZIPOUT_NAME[1]

        try: 
            await send_final(d_ctx, zipname, newDOWNLOAD_ENCRYPTED, shared_gd_folderid)
        except (GDapiError, discord.HTTPException, TaskCancelledError) as e:
            await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)   
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(CreateSave(bot))