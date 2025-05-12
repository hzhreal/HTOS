import os
import discord
import asyncio
import json
import aiofiles
import aiofiles.os
import re
import datetime
import utils.orbis as orbis
from discord.ext import tasks
from aiogoogle import Aiogoogle, HTTPError
from dateutil import parser
from utils.extras import generate_random_string
from utils.constants import SYS_FILE_MAX, MAX_PATH_LEN, MAX_FILENAME_LEN, SEALED_KEY_ENC_SIZE, SAVESIZE_MAX, MOUNT_LOCATION, RANDOMSTRING_LENGTH, PS_UPLOADDIR, SCE_SYS_CONTENTS, MAX_FILES, logger, Color, Embed_t
from utils.exceptions import OrbisError
from utils.conversions import gb_to_bytes, bytes_to_mb

FOLDER_ID_RE = re.compile(r"/folders/([\w-]+)")
GD_LINK_RE = re.compile(r"https://drive\.google\.com/.*")

@tasks.loop(hours=1, reconnect=False)
async def checkGDrive() -> None:
    cur_time = datetime.datetime.now()
    files = await GDapi.list_drive()

    for file in files:
        file_id = file["id"]

        created_time = parser.isoparse(file["createdTime"]) # RFC3339
        day_ahead = created_time + datetime.timedelta(days=1)

        if cur_time.date() >= day_ahead.date():
            await GDapi.delete_file(file_id)

class GDapiError(Exception):
    """Exception raised for errors related to the GDapi class."""
    def __init__(self, message: str) -> None:
        self.message = message

class GDapi:
    """Async functions to interact with the Google Drive API."""
    SAVEGAME_MAX = SAVESIZE_MAX
    TOTAL_SIZE_LIMIT = gb_to_bytes(2)
    MAX_USER_NESTING = 100 # how deep a user can go when uploading files to create a save with
    MAX_FILES_IN_DIR = MAX_FILES
    credentials_path = str(os.getenv("GOOGLE_DRIVE_JSON_PATH"))

    creds = {
        "scopes": ["https://www.googleapis.com/auth/drive"],
        **json.load(open(credentials_path))
    }
    
    @staticmethod
    def grabfolderid(folder_link: str) -> str:
        if not folder_link:
            return ""

        match = FOLDER_ID_RE.search(folder_link)

        if match:
            folder_id = match.group(1)
            return folder_id
        return ""

    @staticmethod
    def is_google_drive_link(text: str) -> bool:
        return bool(GD_LINK_RE.match(text))
    
    @staticmethod
    def getErrStr_HTTPERROR(e: HTTPError) -> str:
        if e.res is None:
            return "HTTPError!"
        
        err = e.res.content.get("error")
        if isinstance(err, dict):
            errCode = err.get("code")
        else:
            logger.error(f"Unexpected GD error (1): {err}")
            return "UNEXPECTED GD ERROR."

        errMsg = []

        err_list = err.get("errors")  
        if isinstance(err_list, list):     
            for error in err_list:
                errMsg.append(error.get("reason"))
        else:
            logger.error(f"Unexpected GD error (2): {err_list}")

        if len(errMsg) == 1:
            errMsg = errMsg[0]
        else:
            errMsg = ", ".join(errMsg)

        return f"Google Drive: HTTPERROR ({errCode}): {errMsg}."
    
    @staticmethod
    def parse_HTTPERROR_simple(e: HTTPError) -> tuple[int, str]:
        if e.res is None:
            raise GDapiError("Failed to upload to Google Drive, please try again.")

        err = e.res.content.get("error")
        if not isinstance(err, dict):
            logger.error(f"Unexpected GD error (1): {err}")
            raise GDapiError("Unexpected GD error!")
        errCode = err.get("code")

        err_list = err.get("errors")
        if not isinstance(err_list, list):
            logger.error(f"Unexpected GD error (2): {err_list}")
            raise GDapiError("Unexpected GD error!")
        errReason = err_list[0].get("reason")

        return errCode, errReason
    
    @staticmethod
    async def fileCheck(
              ctx: discord.ApplicationContext | discord.Message, 
              file_data: list[dict[str, str | int]], 
              sys_files: frozenset[str] | None, 
              ps_save_pair_upload: bool, 
              ignore_filename_check: bool, 
              savesize: int | None = None
            ) -> list[dict[str, str]]:
        
        valid_files_data = []
        total_size = 0

        if ps_save_pair_upload:
            valid_files_data = await GDapi.save_pair_check(ctx, file_data)
            return valid_files_data
        
        for file_info in file_data:
            file_name = file_info["filename"]
            file_id = file_info["fileid"]
            file_size = file_info["filesize"]

            if len(file_name) > MAX_FILENAME_LEN and not ignore_filename_check:
                embfn = discord.Embed(
                    title="Upload alert: Error",
                    description=f"Sorry, the file name of '{file_name}' ({len(file_name)}) exceeds {MAX_FILENAME_LEN}.",
                    colour=Color.DEFAULT.value
                )
                embfn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embfn)
                await asyncio.sleep(1)

            elif file_size > GDapi.SAVEGAME_MAX:
                embFileLarge = discord.Embed(
                    title="Upload alert: Error",
                    description=f"Sorry, the file size of '{file_name}' exceeds the limit of {bytes_to_mb(GDapi.SAVEGAME_MAX)} MB.",
                    colour=Color.DEFAULT.value
                )
                embFileLarge.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embFileLarge)
                await asyncio.sleep(1)

            elif (sys_files is not None) and (file_size > SYS_FILE_MAX or file_name not in sys_files): # sce_sys files are not that big
                embnvSys = discord.Embed(
                    title="Upload alert: Error",
                    description=f"{file_name} is not a valid sce_sys file!",
                    colour=Color.DEFAULT.value
                )
                embnvSys.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embnvSys)
                await asyncio.sleep(1)

            elif savesize is not None and total_size > savesize:
                raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")
            
            else:
                total_size += file_size
                file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                valid_files_data.append(file_data)
        return valid_files_data     

    @staticmethod
    async def save_pair_check(ctx: discord.ApplicationContext | discord.Message, file_data: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
        valid_saves_check1 = []
        for file_info in file_data:
            file_name = file_info["filename"]
            file_size = file_info["filesize"]
            file_id = file_info["fileid"]

            filename = file_name + f"_{'X' * RANDOMSTRING_LENGTH}"
            filename_len = len(filename)
            path_len = len(PS_UPLOADDIR + "/" + filename + "/")

            if filename_len > MAX_FILENAME_LEN:
                embfn = discord.Embed(
                    title="Upload alert: Error",
                    description=f"Sorry, the file name of '{file_name}' ({filename_len}) will exceed {MAX_FILENAME_LEN}.",
                    colour=Color.DEFAULT.value
                )
                embfn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embfn)
                await asyncio.sleep(1)

            elif path_len > MAX_PATH_LEN:
                embpn = discord.Embed(
                    title="Upload alert: Error",
                    description=f"Sorry, the path '{file_name}' ({path_len}) will create exceed ({MAX_PATH_LEN}).",
                    colour=Color.DEFAULT.value
                )
                embpn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embpn)
                await asyncio.sleep(1)
            
            elif file_name.endswith(".bin"):
                if file_size != SEALED_KEY_ENC_SIZE:
                    embnvBin = discord.Embed(
                        title="Upload alert: Error",
                        description=f"Sorry, the file size of '{file_name}' is not {SEALED_KEY_ENC_SIZE} bytes.",
                        colour=Color.DEFAULT.value
                    )
                    embnvBin.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await ctx.edit(embed=embnvBin)
                    await asyncio.sleep(1)

                else:
                    file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                    valid_saves_check1.append(file_data)
            else:
                if file_size > GDapi.SAVEGAME_MAX:
                    embFileLarge = discord.Embed(
                        title="Upload alert: Error",
                        description=f"Sorry, the file size of '{file_name}' exceeds the limit of {bytes_to_mb(GDapi.SAVEGAME_MAX)} MB.",
                        colour=Color.DEFAULT.value
                    )
                    embFileLarge.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await ctx.edit(embed=embFileLarge)
                    await asyncio.sleep(1)
                else:
                    file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                    valid_saves_check1.append(file_data)
        
        valid_saves_final = []
        for file_info in valid_saves_check1:
            file_name = file_info["filename"]
            file_id = file_info["fileid"]
            file_size = file_info["filesize"]
            if file_name.endswith(".bin"): # look for corresponding file

                for file_info_nested in valid_saves_check1:
                    file_name_nested = file_info_nested["filename"]
                    file_id_nested = file_info_nested["fileid"]
                    file_size_nested = file_info_nested["filesize"]
                    if file_name_nested == file_name: 
                        continue

                    elif file_name_nested == os.path.splitext(file_name)[0]:
                        file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                        valid_saves_final.append(file_data)
                        file_data_nested = {"filename": file_name_nested, "fileid": file_id_nested, "filesize": file_size_nested}
                        valid_saves_final.append(file_data_nested)
                        break             
        return valid_saves_final
    
    @classmethod
    async def list_dir(
              cls, 
              ctx: discord.ApplicationContext | discord.Message, 
              folder_id: str,
              sys_files: frozenset[str] | None,
              ps_save_pair_upload: bool,
              ignore_filename_check: bool,
              mounted_len_checks: bool = False,
              cur_nesting: int = 0, 
              total_filesize: int = 0,
              rel_path: str | None = None, 
              files: list[dict[str, str]] | None = None
            ) -> tuple[list[dict[str, str | int]], int]:

        async def warn_filecount(path: str | None) -> None:
            if path is None:
                path = "the root"
            embfn = discord.Embed(
                title="Upload alert: Error",
                description=f"Sorry, the amount of files/folders in {path} exceeds {cls.MAX_FILES_IN_DIR}.",
                colour=Color.DEFAULT.value
            )
            embfn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embfn)
            await asyncio.sleep(3)

        if files is None:
            files = []

        if cur_nesting > cls.MAX_USER_NESTING:
            raise GDapiError(f"Max level nesting of {cls.MAX_USER_NESTING} reached!")

        entries = []
        next_page_token = ""

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            while next_page_token is not None:
                # List files in the folder
                res = await aiogoogle.as_service_account(
                    drive_v3.files.list(
                        q=f"'{folder_id}' in parents and trashed=false", 
                        fields="files(name, id, size, mimeType), nextPageToken",
                        pageSize=1000,
                        pageToken=next_page_token
                    )
                )
                entries.extend(res.get("files", []))
                next_page_token = res.get("nextPageToken")

        count = len(entries)
        if count > cls.MAX_FILES_IN_DIR:
            await warn_filecount(rel_path)
            return files, total_filesize

        file_data_storage = []

        for file_info in entries:
            mimetype = file_info["mimeType"]
            file_name = file_info["name"]
            file_id = file_info["id"]
            file_size = int(file_info.get("size", 0))

            if mimetype == "application/vnd.google-apps.folder":
                if file_name == "." or file_name == ".." or file_name == "sce_sys":
                    continue
                if rel_path is not None:
                    rel_path = os.path.join(rel_path, file_name)
                    rel_path = os.path.normpath(rel_path)
                    if mounted_len_checks:
                        path_len = len(MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + rel_path + "/")
                        if path_len > MAX_PATH_LEN:
                            raise GDapiError(f"Path: {rel_path} ({path_len}) is exceeding {MAX_PATH_LEN}!")
                else:
                    rel_path = file_name
                await cls.list_dir(ctx, file_id, sys_files, ps_save_pair_upload, ignore_filename_check, mounted_len_checks, cur_nesting + 1, total_filesize, rel_path, files)
                # go up one level
                rel_path = os.path.dirname(rel_path)
            else:
                if file_size == 0 or (file_name in SCE_SYS_CONTENTS and sys_files is None):
                    continue
                
                if rel_path is not None:
                    file_path = os.path.join(rel_path, file_name)
                    file_path = os.path.normpath(file_path)
                    if mounted_len_checks:
                        path_len = len(MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + file_path + "/")
                        if len(file_name) > MAX_FILENAME_LEN:
                            raise GDapiError(f"File name ({file_name}) ({len(file_name)}) is exceeding {MAX_FILENAME_LEN}!")
                        elif path_len > MAX_PATH_LEN:
                            raise GDapiError(f"Path: {file_path} ({path_len}) is exceeding {MAX_PATH_LEN}!")
                else:
                    file_path = file_name
            
                file_data = {"filename": file_path, "fileid": file_id, "filesize": file_size}
                file_data_storage.append(file_data)

        valid_file_data = await GDapi.fileCheck(ctx, file_data_storage, sys_files, ps_save_pair_upload, ignore_filename_check)
        for data in valid_file_data:
            file_path = data["filename"]
            file_id = data["fileid"]
            file_size = data["filesize"]

            file_data = {"filepath": file_path, "fileid": file_id, "filesize": file_size} 
            files.append(file_data)
            total_filesize += file_size

        return files, total_filesize

    @classmethod
    async def list_drive(cls) -> list[dict[str, str]]:
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            files = []
            next_page_token = ""

            while next_page_token is not None:
                request = drive_v3.files.list(
                    pageSize=1000,
                    fields="nextPageToken, files(id, createdTime)",
                    pageToken=next_page_token
                )
                
                response = await aiogoogle.as_service_account(request)
                files.extend(response.get("files", []))
                next_page_token = response.get("nextPageToken")
            
            return files

    @classmethod
    async def clear_drive(cls, files: list[dict[str, str]] | None = None) -> None:
        if files is None:
            files = await cls.list_drive()

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            for file in files:
                file_id = file["id"]
                request = drive_v3.files.delete(fileId=file_id)
                await aiogoogle.as_service_account(request)

    @classmethod
    async def delete_file(cls, fileid: str) -> None:
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            request = drive_v3.files.delete(fileId=fileid)
            await aiogoogle.as_service_account(request)

    @classmethod
    async def check_writeperm(cls, folderid: str) -> bool:
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            request = drive_v3.permissions.list(fileId=folderid, fields="permissions")
            try:
                res = await aiogoogle.as_service_account(request)
            except HTTPError as e:
                code, reason = cls.parse_HTTPERROR_simple(e)
                if code == 403 and reason == "insufficientFilePermissions":
                    return False
                raise GDapiError(cls.getErrStr_HTTPERROR(e))

        if res["permissions"][0]["role"] != "writer":
            return False
        return True

    @classmethod
    async def parse_sharedfolder_link(cls, link: str) -> str:
        if not link:
            return ""

        folderid = cls.grabfolderid(link)
        if not folderid:
            raise GDapiError("Invalid shared folder ID!")

        writeperm = await cls.check_writeperm(folderid)
        if not writeperm:
            raise GDapiError("Shared folder has insufficent permissions! Enable write permission.")
        return folderid

    @classmethod
    async def uploadzip(cls, pathToFile: str, fileName: str, shared_folderid: str = "") -> str:
        metadata = {"name": fileName}
        if shared_folderid:
            metadata["parents"] = [shared_folderid]
        
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            
            try:
                response = await aiogoogle.as_service_account(
                    drive_v3.files.create(
                        pipe_from=await aiofiles.open(pathToFile, "rb"), 
                        fields="id", 
                        json=metadata,
                        supportsAllDrives=True
                        )
                )
            except HTTPError as e:
                if e.res is None:
                    raise GDapiError("Failed to upload to Google Drive, please try again.")

                err = e.res.content.get("error")
                errCode = err.get("code")
                errReason = err.get("errors")[0].get("reason")
                if errCode == 403 and errReason == "storageQuotaExceeded":
                    await cls.clear_drive()
                    raise GDapiError("Google drive storage quota was exceeded, tried cleared the storage. Please retry.")
                raise GDapiError(cls.getErrStr_HTTPERROR(e))

            await aiogoogle.as_service_account(
                drive_v3.permissions.create(
                    fileId=response["id"], 
                    json={"role": "reader", "type": "anyone", "allowFileDiscovery": False})
            )

        file_url = f"https://drive.google.com/file/d/{response['id']}"
        
        logger.info(f"Uploaded {pathToFile} to google drive")
        
        return file_url

    @classmethod
    async def downloadsaves_recursive(
              cls, 
              ctx: discord.ApplicationContext | discord.Message, 
              folder_id: str, 
              download_dir: str, 
              max_files: int,
              sys_files: frozenset[str] | None, 
              ps_save_pair_upload: bool, 
              ignore_filename_check: bool,
              allow_duplicates: bool = False
            ) -> list[list[str]]:
        """Setting `ps_save_pair_upload` to `True` will also set `allow_duplicates` to `True`."""
        
        if ps_save_pair_upload:
            allow_duplicates = True

        files, total_filesize = await cls.list_dir(ctx, folder_id, sys_files, ps_save_pair_upload, ignore_filename_check)
        filecount = len(files)
        uploaded_file_paths = []
        if filecount == 0:
            raise GDapiError("Invalid files uploaded, or no files found!")
        elif filecount > max_files:
            raise GDapiError(f"Amount of files cannot exceed {max_files}!")
        elif total_filesize > cls.TOTAL_SIZE_LIMIT:
            raise GDapiError(f"Total size cannot exceed: {bytes_to_mb(cls.TOTAL_SIZE_LIMIT)} MB!")

        if allow_duplicates:
            # enforce no files in root, only dirs
            cur_download_dir = os.path.join(download_dir, os.path.basename(download_dir))
            await aiofiles.os.mkdir(cur_download_dir)
        else:
            cur_download_dir = download_dir

        download_cycle = []
        i = 1
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            for file in files:
                file_name = os.path.basename(file["filepath"])
                file_id = file["fileid"]
                
                download_path = os.path.join(cur_download_dir, file_name)
                if await aiofiles.os.path.exists(download_path):
                    if allow_duplicates:
                        cur_download_dir = os.path.join(download_dir, generate_random_string(RANDOMSTRING_LENGTH))
                        await aiofiles.os.mkdir(cur_download_dir)
                        download_path = os.path.join(cur_download_dir, file_name)
                        uploaded_file_paths.append(download_cycle)
                        download_cycle = []
                    else:
                        continue

                # Download the file
                await aiogoogle.as_service_account(
                    drive_v3.files.get(fileId=file_id, pipe_to=await aiofiles.open(download_path, "wb"), alt="media")
                )
                logger.info(f"Saved {file_name} to {download_path}")
            
                # run a quick check
                if ps_save_pair_upload and not file_name.endswith(".bin"):
                    await orbis.parse_pfs_header(download_path)
                elif ps_save_pair_upload and file_name.endswith(".bin"):
                    await orbis.parse_sealedkey(download_path)

                embeddone = discord.Embed(
                    title="Google drive upload: Retrieved file",
                    description=f"{file_name} has been uploaded and saved ({i}/{filecount}).",
                    colour=Color.DEFAULT.value
                )
                embeddone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embeddone)

                download_cycle.append(download_path)
                i += 1
        uploaded_file_paths.append(download_cycle)
            
        return uploaded_file_paths
    
    @classmethod
    async def downloadfiles_recursive(
              cls, 
              ctx: discord.ApplicationContext | discord.Message, 
              dst_local_dir: str, 
              folder_id: str, 
              max_files: int, 
              savesize: int | None = None
            ) -> list[list[str]]:

        """For encrypt & createsave command."""
        files, total_filesize = await cls.list_dir(ctx, folder_id, None, False, True, mounted_len_checks=True)
        filecount = len(files)
        if filecount == 0:
            raise GDapiError("Invalid files uploaded, or no files found!")
        elif filecount > max_files:
            raise GDapiError(f"Amount of files cannot exceed {max_files}!")
        elif total_filesize > cls.TOTAL_SIZE_LIMIT:
            raise GDapiError(f"Total size cannot exceed: {cls.TOTAL_SIZE_LIMIT}!")
        elif savesize is not None and total_filesize > savesize:
            raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")

        uploaded_file_paths = []
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            i = 1
            for file in files:
                file_path = file["filepath"]
                file_id = file["fileid"]

                download_path = os.path.join(dst_local_dir, file_path)
                await aiofiles.os.makedirs(os.path.dirname(download_path), exist_ok=True)

                # Download the file
                await aiogoogle.as_service_account(
                    drive_v3.files.get(
                        fileId=file_id, 
                        pipe_to=await aiofiles.open(download_path, "wb"), 
                        alt="media")
                )
            
                uploaded_file_paths.append(download_path)

                logger.info(f"Saved {file_path} to {download_path}")
                embeddone = discord.Embed(
                    title="Google drive upload: Retrieved file",
                    description=f"{file_path} has been uploaded and saved ({i}/{filecount}).",
                    colour=Color.DEFAULT.value
                )
                embeddone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embeddone)
                i += 1
     
        return [uploaded_file_paths]
