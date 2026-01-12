import discord
import asyncio
import os
import aiohttp
import aiofiles
import aiofiles.os
import errno

from discord.ext import pages
from dataclasses import dataclass
from typing import Literal, Callable, Awaitable, Any
from enum import Enum
from discord.ui.item import Item
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFoundError, PSNAWPAuthenticationError

from google_drive.gd_functions import gdapi
from google_drive.exceptions import GDapiError
from data.crypto.helpers import extra_import
from network.ftp_functions import FTPps
from utils.orbis import check_saves, parse_pfs_header, parse_sealedkey, checkid, handle_accid
from utils.constants import (
    logger, blacklist_logger, bot, psnawp,
    NPSSO_global, UPLOAD_TIMEOUT, FILE_LIMIT_DISCORD, SCE_SYS_CONTENTS, OTHER_TIMEOUT, MAX_FILES, BLACKLIST_MESSAGE, GENERAL_TIMEOUT, GENERAL_CHUNKSIZE,
    BOT_DISCORD_UPLOAD_LIMIT, MAX_PATH_LEN, MAX_FILENAME_LEN, PSN_USERNAME_RE, MOUNT_LOCATION, RANDOMSTRING_LENGTH, CON_FAIL_MSG, EMBED_DESC_LIM, EMBED_FIELD_LIM
)
from utils.embeds import (
    embgdt, embUtimeout, embnt, emb8, embvalidpsn, cancel_notify_emb,
    embe, embuplSuccess, embuplSuccess1, embencupl,
    embenc_out, embencinst, embgdout, embgames, embgame, embwlcom
)
from utils.exceptions import PSNIDError, FileError, WorkspaceError, TaskCancelledError, OrbisError
from utils.workspace import fetch_accountid_db, write_accountid_db, cleanup, cleanup_simple, write_threadid_db, get_savenames_from_bin_ext, blacklist_check_db
from utils.extras import zipfiles
from utils.conversions import bytes_to_mb
from utils.instance_lock import INSTANCE_LOCK_global

@dataclass
class DiscordContext:
    ctx: discord.ApplicationContext
    msg: discord.Message

class TimeoutHelper:
    """Utilities to pause the process for the user to choose an option, used for discord buttons."""
    def __init__(self, embTimeout: discord.Embed) -> None:
        self.done = False
        self.embTimeout = embTimeout

    async def await_done(self) -> None:
        try:
            while not self.done:  # Continue waiting until done is True
                await asyncio.sleep(1)  # Sleep for 1 second to avoid busy-waiting
        except asyncio.CancelledError:
            pass  # Handle cancellation if needed

    async def handle_timeout(self, ctx: discord.ApplicationContext | discord.Message) -> None:
        await asyncio.sleep(2)
        if not self.done:
            await ctx.edit(embed=self.embTimeout, view=None)
            await asyncio.sleep(4) # make sure user is aware of msg
            self.done = True

class threadButton(discord.ui.View):
    """The panel that allows the user to create a thread to use the bot."""
    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def on_error(self, e: Exception, _: Item, __: discord.Interaction) -> None:
        logger.info(f"Unexpected error while creating thread: {e}", exc_info=True)

    @discord.ui.button(label="Create thread", style=discord.ButtonStyle.primary, custom_id="CreateThread")
    async def callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
        current_instance = INSTANCE_LOCK_global.instances.get(interaction.user.id)
        if current_instance is not None:
            await interaction.response.send_message("You can not create a new thread when you already have an active instance!", ephemeral=True)
            return
        await interaction.response.send_message("Creating thread...", ephemeral=True)

        emb = embwlcom.copy()
        emb.description = emb.description.format(user=interaction.user.name)
        ids_to_remove = []

        try:
            thread = await interaction.channel.create_thread(name=interaction.user.name, auto_archive_duration=10080)
            await thread.send(interaction.user.mention)
            await thread.send(embed=emb)
            ids_to_remove = await write_threadid_db(interaction.user.id, thread.id)
        except (WorkspaceError, discord.Forbidden) as e:
            logger.error(f"Cannot create thread: {e}")

        try:
            for thread_id in ids_to_remove:
                old_thread = bot.get_channel(thread_id)
                if old_thread is not None:
                    await old_thread.delete()
        except discord.Forbidden as e:
            logger.error(f"Cannot clear old thread: {e}")

class UploadMethod(Enum):
    DISCORD = 0
    GOOGLE_DRIVE = 1

class UploadGoogleDriveChoice(Enum):
    STANDARD = 0
    SPECIAL = 1

class ReturnTypes(Enum):
    EXIT = 0
    SUCCESS = 1

@dataclass
class UploadOpt:
    gd_choice: UploadGoogleDriveChoice
    gd_allow_duplicates: bool
    method: UploadMethod | None = None

async def clean_msgs(messages: list[discord.Message]) -> None:
    for msg in messages:
        try:
            await msg.delete()
        except discord.Forbidden:
            pass

async def error_handling(
          ctx: discord.ApplicationContext | discord.Message,
          error: str,
          workspace_folders: list[str] | None,
          uploaded_file_paths: list[str] | None,
          mount_paths: list[str] | None,
          C1ftp: FTPps | None
        ) -> None:
    emb = embe.copy()
    emb.description = emb.description.format(error=error)
    try:
        await ctx.edit(embed=emb)
    except discord.HTTPException as e:
        logger.info(f"Error while editing msg: {e}", exc_info=True)

    if C1ftp is not None and error != CON_FAIL_MSG:
        await cleanup(C1ftp, workspace_folders, uploaded_file_paths, mount_paths)
    else:
        await cleanup_simple(workspace_folders)

"""Makes the bot expect multiple files through discord or google drive."""
def upl_check(message: discord.Message, ctx: discord.ApplicationContext) -> bool:
    if message.author == ctx.author and message.channel == ctx.channel:
        return (len(message.attachments) >= 1) or (message.content and gdapi.is_google_drive_link(message.content)) or (message.content and message.content == "EXIT")

"""Makes the bot expect a single file through discord or google drive."""
def upl1_check(message: discord.Message, ctx: discord.ApplicationContext) -> bool:
    if message.author == ctx.author and message.channel == ctx.channel:
        return (len(message.attachments) == 1) or (message.content and gdapi.is_google_drive_link(message.content)) or (message.content and message.content == "EXIT")

def accid_input_check(message: discord.Message, ctx: discord.ApplicationContext) -> bool:
    if message.author == ctx.author and message.channel == ctx.channel:
        return (message.content and checkid(message.content)) or (message.content and message.content == "EXIT")

def exit_check(message: discord.Message, ctx: discord.ApplicationContext) -> bool:
    if message.author == ctx.author and message.channel == ctx.channel:
        return message.content and message.content == "EXIT"

async def wait_for_msg(ctx: discord.ApplicationContext, check: Callable[[discord.Message, discord.ApplicationContext], bool], embed: discord.Embed | None, delete_response: bool = False, timeout: int | None = OTHER_TIMEOUT) -> discord.Message:
    try:
        response = await bot.wait_for("message", check=lambda message: check(message, ctx), timeout=timeout)
        if delete_response:
            await response.delete()
    except asyncio.TimeoutError:
        if embed is not None:
            await ctx.edit(embed=embed)
            await asyncio.sleep(3)
        raise TimeoutError("TIMED OUT!")
    return response

async def download_attachment(attachment: discord.Attachment, folderpath: str, filename: str | None = None) -> str:
    if filename is None:
        _, ext = os.path.splitext(attachment.filename)
        basename = attachment.title + ext if attachment.title is not None else attachment.filename
        filepath = os.path.join(folderpath, basename)
    else:
        filepath = os.path.join(folderpath, filename)
    try:
        async with aiofiles.open(filepath, "wb") as out:
            async for chunk in attachment.read_chunked(chunksize=GENERAL_CHUNKSIZE):
                await out.write(chunk)
    except asyncio.TimeoutError:
        raise TimeoutError("TIMED OUT!")
    except aiohttp.ClientError:
        raise FileError("Failed to download file.")
    except OSError as e:
        if e.errno == errno.EINVAL:
            raise FileError(f"The filename {os.path.basename(filepath)} is unsupported!")
        raise
    logger.info(f"Saved {attachment.filename} to {filepath}")
    return filepath

async def task_handler(d_ctx: DiscordContext, ordered_tasks: list[Callable[[], Awaitable[Any]]], ordered_embeds: list[discord.Embed]) -> list[Any]:
    tasks_len = len(ordered_tasks)
    embeds_len = len(ordered_embeds)
    assert tasks_len >= embeds_len

    result = []
    cancel_task = None
    for i in range(tasks_len):
        embed = None
        if i < embeds_len:
            embed = ordered_embeds[i]

        main_task = asyncio.create_task(ordered_tasks[i]())
        if cancel_task is None:
            cancel_task = asyncio.create_task(wait_for_msg(d_ctx.ctx, exit_check, None, timeout=GENERAL_TIMEOUT))

        if embed is not None:
            try:
                await d_ctx.msg.edit(embed=embed)
            except discord.HTTPException as e:
                logger.info(f"Error while editing msg: {e}", exc_info=True)

        done, _ = await asyncio.wait(
            {main_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED
        )
        if main_task in done:
            try:
                res = await main_task
                result.append(res)
            except Exception:
                cancel_task.cancel()
                try:
                    await cancel_task
                except (asyncio.CancelledError, TimeoutError):
                    pass
                except Exception as e:
                    logger.exception(f"Unexpected error: {e}")
                raise
        else:
            main_task.cancel()
            try:
                await main_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")

            try:
                await cancel_task
            except TimeoutError as e:
                raise TaskCancelledError(e)
            raise TaskCancelledError("CANCELLED!")

    cancel_task.cancel()
    try:
        await cancel_task
    except (asyncio.CancelledError, TimeoutError):
        pass
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")

    return result

async def upload2(
          d_ctx: DiscordContext,
          save_location: str,
          max_files: int,
          sys_files: bool,
          ps_save_pair_upload: bool,
          ignore_filename_check: bool,
          savesize: int | None = None,
          opt: UploadOpt | None = None
        ) -> list[list[str]]:

    if opt is None:
        opt = UploadOpt(UploadGoogleDriveChoice.STANDARD, False)

    message = await wait_for_msg(d_ctx.ctx, upl_check, embUtimeout, timeout=UPLOAD_TIMEOUT)

    if len(message.attachments) > max_files:
        raise FileError(f"Attachments uploaded cannot exceed {max_files}!")

    elif len(message.attachments) >= 1:
        attachments = message.attachments
        uploaded_file_paths = []
        download_cycle = []

        valid_attachments = await check_saves(d_ctx.msg, attachments, ps_save_pair_upload, sys_files, ignore_filename_check, savesize)
        filecount = len(valid_attachments)
        if filecount == 0:
            raise FileError("Invalid files uploaded, or no files found!")

        await d_ctx.msg.edit(embed=cancel_notify_emb)
        await asyncio.sleep(1)

        i = 1
        for attachment in valid_attachments:
            task = [lambda: download_attachment(attachment, save_location)]
            file_path = (await task_handler(d_ctx, task, []))[0]

            # run a quick check
            if ps_save_pair_upload and not attachment.filename.endswith(".bin"):
                await parse_pfs_header(file_path)
            elif ps_save_pair_upload and attachment.filename.endswith(".bin"):
                await parse_sealedkey(file_path)

            emb = embuplSuccess.copy()
            emb.description = emb.description.format(filename=attachment.filename, i=i, filecount=filecount)
            await d_ctx.msg.edit(embed=emb)

            download_cycle.append(file_path)
            i += 1
        uploaded_file_paths.append(download_cycle)
        opt.method = UploadMethod.DISCORD
        await message.delete() # delete afterwards for reliability

    elif message.content == "EXIT":
        raise TimeoutError("EXITED!")

    else:
        try:
            google_drive_link = message.content
            await message.delete()
            folder_id = gdapi.grabfolderid(google_drive_link)
            if not folder_id:
                raise GDapiError("Could not find the folder id!")
            if opt.gd_choice == UploadGoogleDriveChoice.STANDARD:
                task = [lambda: gdapi.downloadsaves_recursive(d_ctx.msg, folder_id, save_location, max_files, SCE_SYS_CONTENTS if sys_files else None, ps_save_pair_upload, ignore_filename_check, opt.gd_allow_duplicates)]
            else:
                task = [lambda: gdapi.downloadfiles_recursive(d_ctx.msg, save_location, folder_id, max_files, savesize)]
            await d_ctx.msg.edit(embed=cancel_notify_emb)
            await asyncio.sleep(1)
            uploaded_file_paths = (await task_handler(d_ctx, task, []))[0]

        except asyncio.TimeoutError:
            await d_ctx.msg.edit(embed=embgdt)
            raise TimeoutError("TIMED OUT!")

        opt.method = UploadMethod.GOOGLE_DRIVE

    return uploaded_file_paths

async def upload1(d_ctx: DiscordContext, save_location: str) -> str:
    message = await wait_for_msg(d_ctx.ctx, upl_check, embUtimeout, timeout=UPLOAD_TIMEOUT)

    if len(message.attachments) == 1:
        attachment = message.attachments[0]

        if len(attachment.filename) > MAX_FILENAME_LEN:
            await message.delete()
            raise FileError(f"Filename: {attachment.filename} ({len(attachment.filename)}) is exceeding {MAX_FILENAME_LEN}!")

        elif attachment.size > FILE_LIMIT_DISCORD:
            await message.delete()
            raise FileError(f"DISCORD UPLOAD ERROR: File size of '{attachment.filename}' exceeds the limit of {bytes_to_mb(FILE_LIMIT_DISCORD)} MB.")

        else:
            task = [lambda: download_attachment(attachment, save_location)]
            file_path = (await task_handler(d_ctx, task, []))[0]

            emb = embuplSuccess1.copy()
            emb.description = emb.description.format(filename=attachment.filename)
            await message.delete()
            await d_ctx.msg.edit(embed=emb)

    elif message.content == "EXIT":
        raise TimeoutError("EXITED!")

    else:
        try:
            google_drive_link = message.content
            await message.delete()
            folder_id = gdapi.grabfolderid(google_drive_link)
            if not folder_id:
                raise GDapiError("Could not find the folder id!")
            task = [lambda: gdapi.downloadfiles_recursive(d_ctx.msg, save_location, folder_id, 1)]
            files = await task_handler(d_ctx, task, [])
            file_path = files[0][0][0]

        except asyncio.TimeoutError:
            await d_ctx.msg.edit(embed=embgdt)
            raise TimeoutError("TIMED OUT!")

    return file_path

async def upload2_special(d_ctx: DiscordContext, saveLocation: str, max_files: int, splitvalue: str, savesize: int | None = None) -> list[str]:
    message = await wait_for_msg(d_ctx.ctx, upl_check, embUtimeout, timeout=UPLOAD_TIMEOUT)

    if len(message.attachments) > max_files:
        raise FileError(f"Attachments uploaded cannot exceed {max_files}!")

    elif len(message.attachments) >= 1:
        attachments = message.attachments
        uploaded_file_paths = []

        valid_attachments = await check_saves(d_ctx.msg, attachments, False, False, True, savesize)
        filecount = len(valid_attachments)
        if filecount == 0:
            raise FileError("Invalid files uploaded!")

        await d_ctx.msg.edit(embed=cancel_notify_emb)
        await asyncio.sleep(1)

        i = 1
        for attachment in valid_attachments:
            rel_file_path = attachment.filename.split(splitvalue)
            rel_file_path = "/".join(rel_file_path)
            rel_file_path = os.path.normpath(rel_file_path)
            path_len = len(MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + rel_file_path + "/")

            file_name = os.path.basename(rel_file_path)
            if len(file_name) > MAX_FILENAME_LEN:
                raise FileError(f"File name ({file_name}) ({len(file_name)}) is exceeding {MAX_FILENAME_LEN}!")

            elif path_len > MAX_PATH_LEN:
                raise FileError(f"Path: {rel_file_path} ({path_len}) is exceeding {MAX_PATH_LEN}!")

            dir_path = os.path.join(saveLocation, os.path.dirname(rel_file_path))
            await aiofiles.os.makedirs(dir_path, exist_ok=True)
            task = [lambda: download_attachment(attachment, dir_path)]
            full_path = (await task_handler(d_ctx, task, []))[0]

            emb = embuplSuccess.copy()
            emb.description = emb.description.format(filename=rel_file_path, i=i, filecount=filecount)  
            await d_ctx.msg.edit(embed=emb)

            uploaded_file_paths.append(full_path)
            i += 1

        await message.delete()

    elif message.content == "EXIT":
        raise TimeoutError("EXITED!")

    else:
        try:
            google_drive_link = message.content
            await message.delete()
            folder_id = gdapi.grabfolderid(google_drive_link)
            if not folder_id: 
                raise GDapiError("Could not find the folder id!")
            task = [lambda: gdapi.downloadfiles_recursive(d_ctx.msg, saveLocation, folder_id, max_files, savesize)]
            await d_ctx.msg.edit(embed=cancel_notify_emb)
            await asyncio.sleep(1)
            uploaded_file_paths = (await task_handler(d_ctx, task, []))[0][0]
        except asyncio.TimeoutError:
            await d_ctx.msg.edit(embed=embgdt)
            raise TimeoutError("TIMED OUT!")

    return uploaded_file_paths

async def psusername(ctx: discord.ApplicationContext, username: str) -> str:
    """Used to obtain an account ID, either through converting from username, obtaining from db, or manually. Utilizes the PSN API or a website doing it for us."""
    user_id = ""

    if username == "":
        user_id = await fetch_accountid_db(ctx.author.id)
        if user_id is not None:
            # check blacklist while we are at it
            search = await blacklist_check_db(None, user_id)
            if search[0]:
                blacklist_logger.info(f"{ctx.author.name} ({ctx.author.id}) used a blacklisted account ID: {user_id}")
                msg = BLACKLIST_MESSAGE
                reason = search[1]
                if reason is not None:
                    msg += f"\n{reason}"
                raise PSNIDError(msg)
            return user_id
        else:
            raise PSNIDError("Could not find previously stored account ID.")

    if len(username) < 3 or len(username) > 16:
        await asyncio.sleep(1)
        raise PSNIDError("Invalid PS username!")
    elif not bool(PSN_USERNAME_RE.fullmatch(username)):
        await asyncio.sleep(1)
        raise PSNIDError("Invalid PS username!")

    if NPSSO_global.val:
        try:
            user = psnawp.user(online_id=username)
            user_id = user.account_id
            user_id = handle_accid(user_id)
            delmsg = False

        except PSNAWPNotFoundError:
            await ctx.respond(embed=emb8)
            delmsg = True

            response = await wait_for_msg(ctx, accid_input_check, embnt, delete_response=True)
            if response.content == "EXIT":
                raise PSNIDError("EXITED!")
            user_id = response.content
        except PSNAWPAuthenticationError:
            NPSSO_global.val = ""

    if not user_id:
        raise PSNIDError("Account ID fetcher is unavailable. Use the `store_accountid` command.")

    if delmsg:
        await asyncio.sleep(0.5)
        await ctx.edit(embed=embvalidpsn)
    else:
        await ctx.respond(embed=embvalidpsn)

    await asyncio.sleep(0.5)

    # check blacklist while we are at it
    search = await blacklist_check_db(None, user_id)
    if search[0]:
        blacklist_logger.info(f"{ctx.author.name} ({ctx.author.id}) used a blacklisted account ID: {user_id}")
        msg = BLACKLIST_MESSAGE
        reason = search[1]
        if reason is not None:
            msg += f"\n{reason}"
        raise PSNIDError(msg)

    await write_accountid_db(ctx.author.id, user_id.lower())
    return user_id.lower()

async def replace_decrypted(
          d_ctx: DiscordContext,
          fInstance: FTPps,
          files: list[str],
          titleid: str,
          mount_location: str,
          upload_individually: bool,
          local_download_path: str,
          savepair_name: str,
          savesize: int,
          ignore_secondlayer_checks: bool
        ) -> list[str]:

    """Used in the encrypt command to replace files one by one, or how many you want at once."""
    from utils.namespaces import Crypto
    completed = []
    if upload_individually:
        total_count = 0
        for file in files:
            fullPath = mount_location + "/" + file
            cwd_here = fullPath.split("/")
            last_N = cwd_here.pop(len(cwd_here) - 1)
            cwd_here = "/".join(cwd_here)

            emb = embencupl.copy()
            emb.title = emb.title.format(savename=savepair_name)
            emb.description = emb.description.format(filename=file)
            await d_ctx.msg.edit(embed=emb)

            attachment_path = await upload1(d_ctx, local_download_path)
            new_path = os.path.join(local_download_path, last_N)
            await aiofiles.os.rename(attachment_path, new_path)

            if not ignore_secondlayer_checks:
                await extra_import(Crypto, titleid, new_path)

            task = [lambda: fInstance.replacer(cwd_here, last_N)]
            await task_handler(d_ctx, task, [])
            completed.append(file)
            total_count += await aiofiles.os.path.getsize(new_path)
        if total_count > savesize:
            raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")

    else:
        async def send_chunk(msg_container: list[discord.Message], chunk: str) -> None:
            emb = embenc_out.copy()
            emb.title = emb.title.format(savename=savepair_name)
            emb.description = emb.description = chunk
            msg = await d_ctx.ctx.send(embed=emb)
            msg_container.append(msg)
            await asyncio.sleep(1)

        SPLITVALUE = "SLASH"

        emb = embencinst.copy()
        emb.title = emb.title.format(savename=savepair_name)
        emb.description = emb.description.format(splitvalue=SPLITVALUE)
        await d_ctx.msg.edit(embed=emb)
        await asyncio.sleep(2)

        msg_container: list[discord.Message] = []
        current_chunk = ""
        for line in files:
            if len(current_chunk) + len(line) + 1 > EMBED_DESC_LIM:
                await send_chunk(msg_container, current_chunk)
                current_chunk = ""

            if current_chunk:
                current_chunk += "\n"
            current_chunk += line
        if current_chunk:
            await send_chunk(msg_container, current_chunk)

        opt = UploadOpt(UploadGoogleDriveChoice.SPECIAL, False)
        uploaded_file_paths = (await upload2(d_ctx, local_download_path, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False, ignore_filename_check=True, savesize=savesize, opt=opt))[0]

        for msg in msg_container:
            await msg.delete(delay=0.5)

        if opt.method == UploadMethod.DISCORD:
            for path in uploaded_file_paths:
                file = os.path.basename(path)
                file_constructed = file.split(SPLITVALUE)
                if file_constructed[0] == "": 
                    file_constructed = file_constructed[1:]
                file_constructed = "/".join(file_constructed)

                if file_constructed not in files:
                    await aiofiles.os.remove(path)

                else:
                    for savefile in files:
                        if file_constructed == savefile:
                            last_N = os.path.basename(savefile)
                            cwd_here = savefile.split("/")
                            cwd_here = cwd_here[:-1]
                            cwd_here = "/".join(cwd_here)
                            cwd_here = mount_location + "/" + cwd_here

                            file_renamed = os.path.join(local_download_path, last_N)
                            await aiofiles.os.rename(path, file_renamed)

                            if not ignore_secondlayer_checks:
                                await extra_import(Crypto, titleid, file_renamed)

                            task = [lambda: fInstance.replacer(cwd_here, last_N)]
                            await task_handler(d_ctx, task, [])
                            completed.append(last_N)
        else:
            task = [lambda: fInstance.upload_folder(mount_location, local_download_path)]
            await task_handler(d_ctx, task, [])
            idx = len(local_download_path) + (local_download_path[-1] != os.path.sep)
            completed.extend([x[idx:] for x in uploaded_file_paths])

    if len(completed) == 0:
        raise FileError("Could not replace any files!")

    return completed

async def send_final(d_ctx: DiscordContext, file_name: str, zipupPath: str, shared_gd_folderid: str = "", extra_msg: str = "") -> None:
    """Zips path and uploads file through discord or google drive depending on the size."""
    zipfiles(zipupPath, file_name)
    final_file = os.path.join(zipupPath, file_name)
    final_size = await aiofiles.os.path.getsize(final_file)

    if final_size < BOT_DISCORD_UPLOAD_LIMIT and not shared_gd_folderid:
        try:
            task = [lambda: d_ctx.ctx.send(content=extra_msg, file=discord.File(final_file), reference=d_ctx.msg)]
            await task_handler(d_ctx, task, [])
        except asyncio.TimeoutError:
            raise TimeoutError("TIMED OUT!")
        except aiohttp.ClientError:
            raise FileError("Failed to upload file.")
    else:
        task = [lambda: gdapi.uploadzip(d_ctx.msg, final_file, file_name, shared_gd_folderid)]
        file_url = await task_handler(d_ctx, task, [])
        emb = embgdout.copy()
        emb.description = emb.description.format(url=file_url[0], extra_msg=extra_msg)
        await d_ctx.ctx.send(embed=emb, reference=d_ctx.msg)

def qr_check(message: discord.Message, ctx: discord.ApplicationContext, max_index: int, exit_val: str) -> str | bool:
    if message.author == ctx.author and message.channel == ctx.channel:
        if message.content == exit_val:
            return message.content
        else:
            try:
                index = int(message.content)
                return 1 <= index <= max_index
            except ValueError:
                return False
    return False

async def qr_interface_main(d_ctx: DiscordContext, stored_saves: dict[str, dict[str, dict[str, str]]]) -> tuple[str, dict[str, dict[str, str]]] | tuple[Literal["EXIT"], Literal["EXIT"]]:
    game_desc = ""
    game_msgs = []
    selection = {}
    entries_added = 0

    emb = embgames.copy()

    for game, _ in stored_saves.items():
        game_info = f"\n{entries_added + 1}. {game}"
        if len(game_desc + game_info) <= EMBED_DESC_LIM:
            game_desc += game_info
        else:
            emb.description = emb.description = game_desc
            msg = await d_ctx.ctx.respond(embed=emb)
            game_msgs.append(msg)
            game_desc = game_info
        selection[entries_added] = game
        entries_added += 1
    if game_desc:
        emb.description = emb.description = game_desc
        msg = await d_ctx.ctx.respond(embed=emb)
        game_msgs.append(msg)

    if entries_added == 0:
        raise WorkspaceError("NO STORED SAVES!")

    try:
       message = await bot.wait_for("message", check=lambda message: qr_check(message, d_ctx.ctx, entries_added, "EXIT"), timeout=OTHER_TIMEOUT) 
    except asyncio.TimeoutError:
        await clean_msgs(game_msgs)
        raise TimeoutError("TIMED OUT!")

    await message.delete()
    await clean_msgs(game_msgs)

    if message.content == "EXIT":
        return message.content, message.content

    else:
        game = selection[int(message.content) - 1]
        selected_game = stored_saves.get(game)
        if not selected_game:
            raise WorkspaceError("Could not find game!")
        return game, selected_game

async def run_qr_paginator(d_ctx: DiscordContext, stored_saves: dict[str, dict[str, dict[str, str]]]) -> tuple[ReturnTypes, list[str]]:
    while True:
        game, game_dict = await qr_interface_main(d_ctx, stored_saves)
        if game == "EXIT" and game_dict == "EXIT":
            return ReturnTypes.EXIT, []

        pages_list = []
        selection = {}
        entries_added = 0 # no limit
        fields_added = 0 # stays within limit
        emb = embgame.copy()
        emb.title = game

        for titleId, titleId_dict in game_dict.items():
            for savedesc, path in titleId_dict.items():
                if fields_added == EMBED_FIELD_LIM:
                    pages_list.append(emb)
                    emb = emb.copy()
                    emb.clear_fields()
                    fields_added = 0

                emb.add_field(name=titleId, value=f"{entries_added + 1}. {savedesc}")
                selection[entries_added] = path
                entries_added += 1
                fields_added += 1
        pages_list.append(emb)

        if entries_added == 0:
            raise WorkspaceError("NO STORED SAVES!")

        paginator = pages.Paginator(pages=pages_list, show_disabled=False, timeout=None)
        p_msg = await paginator.respond(d_ctx.ctx.interaction)

        try:
            message: discord.Message = await bot.wait_for("message", check=lambda message: qr_check(message, d_ctx.ctx, entries_added, "BACK"), timeout=OTHER_TIMEOUT) 
        except asyncio.TimeoutError:
            await paginator.disable(page=pages_list[0])
            await p_msg.delete()
            raise TimeoutError("TIMED OUT!")

        await message.delete()

        await paginator.disable(page=pages_list[0])
        await p_msg.delete()

        if message.content == "BACK":
            continue

        else:
            selected_save = selection[int(message.content) - 1]
            savenames = await get_savenames_from_bin_ext(selected_save)
            if len(savenames) == 0:
                raise WorkspaceError("Failed to get saves!")
            return ReturnTypes.SUCCESS, [os.path.join(selected_save, x) for x in savenames]
