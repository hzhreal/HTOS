import os
import discord
import asyncio
import json
import aiofiles
import aiofiles.os
import re
import datetime
import aiohttp
import utils.orbis as orbis
from discord.ext import tasks
from aiogoogle import Aiogoogle, auth, HTTPError, models
from dateutil import parser
from enum import Enum, auto

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.extras import generate_random_string
from utils.constants import SYS_FILE_MAX, MAX_PATH_LEN, MAX_FILENAME_LEN, SEALED_KEY_ENC_SIZE, SAVESIZE_MAX, MOUNT_LOCATION, RANDOMSTRING_LENGTH, PS_UPLOADDIR, SCE_SYS_CONTENTS, MAX_FILES, logger, Color, Embed_t, gd_upl_progress_emb
from utils.exceptions import OrbisError
from utils.conversions import gb_to_bytes, bytes_to_mb, mb_to_bytes, round_half_up, minutes_to_seconds

FOLDER_ID_RE = re.compile(r"/folders/([\w-]+)")
GD_LINK_RE = re.compile(r"https://drive\.google\.com/.*")

class GDapiError(Exception):
    """Exception raised for errors related to the GDapi class."""
    def __init__(self, message: str) -> None:
        self.message = message

class GDapi:
    class AccountType(Enum):
        SERVICE_ACCOUNT = auto()
        PERSONAL_ACCOUNT = auto()

    """Async functions to interact with the Google Drive API."""
    SAVEGAME_MAX = SAVESIZE_MAX
    TOTAL_SIZE_LIMIT = gb_to_bytes(2)
    MAX_USER_NESTING = 100 # how deep a user can go when uploading files to create a save with
    MAX_FILES_IN_DIR = MAX_FILES
    UPLOAD_CHUNKSIZE = mb_to_bytes(32)
    UPLOAD_CHUNK_TIMEOUT = aiohttp.ClientTimeout(
        total=minutes_to_seconds(10), 
        sock_connect=30
    )
    RANGE_PATTERN = re.compile(r"bytes=(\d+)-(\d+)")

    def __init__(self) -> None:
        assert self.UPLOAD_CHUNKSIZE % (256 * 1024) == 0
        self.authorize()

    def authorize(self) -> None:
        CREDENTIALS_PATH = str(os.getenv("GOOGLE_DRIVE_JSON_PATH"))
        SCOPE = ["https://www.googleapis.com/auth/drive"]

        if not os.path.isfile(CREDENTIALS_PATH):
            raise GDapiError("Credentials path does not exist or is not a file!")

        # check if it is a service account
        serviceacc_creds = {
            "scopes": SCOPE,
            **json.load(open(CREDENTIALS_PATH))
        }
        acc_type = serviceacc_creds.get("type", "")
        if acc_type == "service_account":
            self.creds = {"service_account_creds": serviceacc_creds}
            self.account_type = self.AccountType.SERVICE_ACCOUNT
            return
        
        CACHED_CREDENTIALS_PATH = os.path.join(os.path.dirname(CREDENTIALS_PATH), "token.json")

        # try to get cached oauth credentials
        if os.path.isfile(CACHED_CREDENTIALS_PATH):
            try:
                creds = Credentials.from_authorized_user_file(CACHED_CREDENTIALS_PATH, SCOPE)
            except ValueError:
                creds = None
        else:
            creds = None

        if not creds or not creds.valid:
            # refresh or obtain oauth credentials
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPE)
                creds = flow.run_local_server(port=0)
            with open(CACHED_CREDENTIALS_PATH, "w") as token:
                token.write(creds.to_json())
        build("drive", "v3", credentials=creds)

        client_creds = auth.creds.ClientCreds(
            creds.client_id,
            creds.client_secret,
            creds.scopes
        )
        user_creds = auth.creds.UserCreds(
            refresh_token=creds.refresh_token,
            scopes=creds.scopes,
            id_token=creds.id_token,
            token_uri=creds.token_uri
        )
        self.creds = {"client_creds": client_creds, "user_creds": user_creds}
        self.account_type = self.AccountType.PERSONAL_ACCOUNT

    async def send_req(self, aiogoogle: Aiogoogle, req: models.Request, full_res: bool = False) -> models.Response:
        match self.account_type:
            case self.AccountType.SERVICE_ACCOUNT:
                return await aiogoogle.as_service_account(req, full_res=full_res)
            case self.AccountType.PERSONAL_ACCOUNT:
                return await aiogoogle.as_user(req, full_res=full_res)

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
    
    async def list_dir(
              self, 
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
                description=f"Sorry, the amount of files/folders in {path} exceeds {self.MAX_FILES_IN_DIR}.",
                colour=Color.DEFAULT.value
            )
            embfn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embfn)
            await asyncio.sleep(3)

        if files is None:
            files = []

        if cur_nesting > self.MAX_USER_NESTING:
            raise GDapiError(f"Max level nesting of {self.MAX_USER_NESTING} reached!")

        entries = []
        next_page_token = ""

        async with Aiogoogle(**self.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            while next_page_token is not None:
                req = drive_v3.files.list(
                    q=f"'{folder_id}' in parents and trashed=false", 
                    fields="files(name, id, size, mimeType), nextPageToken",
                    pageSize=1000,
                    pageToken=next_page_token
                )

                res = await self.send_req(aiogoogle, req)

                entries.extend(res.get("files", []))
                next_page_token = res.get("nextPageToken")

        count = len(entries)
        if count > self.MAX_FILES_IN_DIR:
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
                await self.list_dir(ctx, file_id, sys_files, ps_save_pair_upload, ignore_filename_check, mounted_len_checks, cur_nesting + 1, total_filesize, rel_path, files)
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

    async def list_drive(self) -> list[dict[str, str]]:
        async with Aiogoogle(**self.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            files = []
            next_page_token = ""

            while next_page_token is not None:
                req = drive_v3.files.list(
                    q="'me' in owners",
                    pageSize=1000,
                    fields="nextPageToken, files(id, createdTime)",
                    pageToken=next_page_token
                )
                
                res = await self.send_req(aiogoogle, req)
                files.extend(res.get("files", []))
                next_page_token = res.get("nextPageToken")
            
            return files

    async def clear_drive(self, files: list[dict[str, str]] | None = None) -> None:
        if files is None:
            try:
                files = await self.list_drive()
            except HTTPError as e:
                logger.error(f"Failed to list drive: {e}")
                return

        for file in files:
            file_id = file["id"]
            try:
                await self.delete_file(file_id)
            except HTTPError:
                pass

    async def check_drive_storage(self) -> bool:
        async with Aiogoogle(**self.creds) as aiogoogle:
            try:
                drive_v3 = await aiogoogle.discover("drive", "v3")

                req = drive_v3.about.get(
                    fields="storageQuota"
                )
                res = await self.send_req(aiogoogle, req)
            except HTTPError as e:
                logger.error(f"GD-Error while checking drive storage: {e}")
                raise GDapiError("Failed to check drive storage!")
        storage_quota = res["storageQuota"]
        if storage_quota:
            limit = int(storage_quota["limit"])
            usage = int(storage_quota["usage"])
            return (limit - usage) >= self.TOTAL_SIZE_LIMIT
        return False

    async def delete_file(self, fileid: str) -> None:
        async with Aiogoogle(**self.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            req = drive_v3.files.get(fileId=fileid, fields="capabilities")
            res = await self.send_req(aiogoogle, req)
           
            can_delete = res.get("capabilities", {}).get("canDelete", False)

            if can_delete:
                req = drive_v3.files.delete(fileId=fileid)
                await self.send_req(aiogoogle, req)

    async def check_writeperm(self, folderid: str) -> bool:
        async with Aiogoogle(**self.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            req = drive_v3.permissions.list(fileId=folderid, fields="permissions")
            try:
                res = await self.send_req(aiogoogle, req)
            except HTTPError as e:
                code, reason = self.parse_HTTPERROR_simple(e)
                if code == 403 and reason == "insufficientFilePermissions":
                    return False
                raise GDapiError(self.getErrStr_HTTPERROR(e))

        if res["permissions"][0]["role"] != "writer":
            return False
        return True

    async def parse_sharedfolder_link(self, link: str) -> str:
        if not link:
            return ""

        folderid = self.grabfolderid(link)
        if not folderid:
            raise GDapiError("Invalid shared folder ID!")

        writeperm = await self.check_writeperm(folderid)
        if not writeperm:
            raise GDapiError("Shared folder has insufficent permissions! Enable write permission.")
        return folderid

    async def uploadzip(self, ctx: discord.ApplicationContext | discord.Message, file_path: str, file_name: str, shared_folderid: str = "") -> str:
        metadata = {"name": file_name}
        if shared_folderid:
            metadata["parents"] = [shared_folderid]
        filesize = await aiofiles.os.path.getsize(file_path)

        # Initial request for resumable upload
        async with Aiogoogle(**self.creds) as aiogoogle:
            try:
                drive_v3 = await aiogoogle.discover("drive", "v3")
                req_init = models.Request(
                    method="POST",
                    url="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id&supportsAllDrives=True",
                    json=metadata,
                    headers={
                        "X-Upload-Content-Length": str(filesize),
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                    upload_file_content_type="application/zip"
                )
                res_init = await self.send_req(aiogoogle, req_init, full_res=True)
                location = res_init.headers["Location"]
            except HTTPError as e:
                raise GDapiError(self.getErrStr_HTTPERROR(e))

        # Upload in chunks
        file_id = None
        start_pos = 0
        file = await aiofiles.open(file_path, "rb")
        emb = gd_upl_progress_emb.copy()
        async with aiohttp.ClientSession(timeout=self.UPLOAD_CHUNK_TIMEOUT) as session:
            while start_pos < filesize:
                emb.description = f"{round_half_up((start_pos / filesize) * 100)}%"
                await ctx.edit(embed=emb)

                await file.seek(start_pos)
                chunk = await file.read(self.UPLOAD_CHUNKSIZE)
                chunk_size = len(chunk)
                end_pos = start_pos + chunk_size - 1

                try:
                    async with session.put(
                        url=location,
                        data=chunk,
                        headers={
                            "Content-Length": str(chunk_size),
                            "Content-Range": f"bytes {start_pos}-{end_pos}/{filesize}"
                        }
                    ) as upload_res:
                        if upload_res.status >= 400:
                            try:
                                body = await upload_res.json()
                            except aiohttp.ContentTypeError:
                                body = await upload_res.text()
                            logger.error(
                                f"Google Drive upload failed:\n"
                                f"Status: {upload_res.status} {upload_res.reason}\n"
                                f"Response body: {body}"
                            )
                            raise GDapiError(f"Upload failed with status code {upload_res.status}!")
                        
                        if upload_res.status == 308:
                            range_header = upload_res.headers.get("Range", "")
                            range_pos = self.RANGE_PATTERN.fullmatch(range_header)
                            if not range_pos:
                                # If Range is not present then no bytes were receieved, but we will not be retrying
                                raise GDapiError("Unexpected error!")
                            start_pos = int(range_pos.group(2)) + 1
                        elif upload_res.status in (200, 201):
                            try:
                                body = await upload_res.json()
                            except aiohttp.ContentTypeError:
                                await file.close()
                                raise GDapiError("Unexpected error!")
                            file_id = body["id"]
                            emb.description = "100%"
                            await ctx.edit(embed=emb)
                            logger.info(f"Uploaded {file_path} to google drive")
                            break
                        else:
                            logger.error(
                                f"Google Drive upload: Unexpected status code:\n"
                                f"Status: {upload_res.status} {upload_res.reason}\n"
                                f"Response body: {body}"
                            )
                            raise GDapiError(f"Upload failed with status code {upload_res.status}!")
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    await file.close()
                    logger.error(f"GD chunk upload request error: {e}")
                    raise GDapiError("Error while uploading chunk!")
                except Exception:
                    await file.close()
                    raise
        await file.close()

        # Set permissions
        async with Aiogoogle(**self.creds) as aiogoogle:
            try:
                drive_v3 = await aiogoogle.discover("drive", "v3")

                perm_req = drive_v3.permissions.create(
                    fileId=file_id, 
                    json={"role": "reader", "type": "anyone", "allowFileDiscovery": False}
                )
                await self.send_req(aiogoogle, perm_req)
            except HTTPError as e:
                raise GDapiError(self.getErrStr_HTTPERROR(e))

        file_url = f"https://drive.google.com/file/d/{file_id}"
        return file_url

    async def downloadsaves_recursive(
              self, 
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

        files, total_filesize = await self.list_dir(ctx, folder_id, sys_files, ps_save_pair_upload, ignore_filename_check)
        filecount = len(files)
        uploaded_file_paths = []
        if filecount == 0:
            raise GDapiError("Invalid files uploaded, or no files found!")
        elif filecount > max_files:
            raise GDapiError(f"Amount of files cannot exceed {max_files}!")
        elif total_filesize > self.TOTAL_SIZE_LIMIT:
            raise GDapiError(f"Total size cannot exceed: {bytes_to_mb(self.TOTAL_SIZE_LIMIT)} MB!")

        if allow_duplicates:
            # enforce no files in root, only dirs
            cur_download_dir = os.path.join(download_dir, os.path.basename(download_dir))
            await aiofiles.os.mkdir(cur_download_dir)
        else:
            cur_download_dir = download_dir

        download_cycle = []
        i = 1
        async with Aiogoogle(**self.creds) as aiogoogle:
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
                        
                async with aiofiles.open(download_path, "wb") as file:
                    req = drive_v3.files.get(
                        fileId=file_id, pipe_to=file, alt="media"
                    )
                    await self.send_req(aiogoogle, req)
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
    
    async def downloadfiles_recursive(
              self, 
              ctx: discord.ApplicationContext | discord.Message, 
              dst_local_dir: str, 
              folder_id: str, 
              max_files: int, 
              savesize: int | None = None
            ) -> list[list[str]]:

        """For encrypt & createsave command."""
        files, total_filesize = await self.list_dir(ctx, folder_id, None, False, True, mounted_len_checks=True)
        filecount = len(files)
        if filecount == 0:
            raise GDapiError("Invalid files uploaded, or no files found!")
        elif filecount > max_files:
            raise GDapiError(f"Amount of files cannot exceed {max_files}!")
        elif total_filesize > self.TOTAL_SIZE_LIMIT:
            raise GDapiError(f"Total size cannot exceed: {self.TOTAL_SIZE_LIMIT}!")
        elif savesize is not None and total_filesize > savesize:
            raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")

        uploaded_file_paths = []
        async with Aiogoogle(**self.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            i = 1
            for file in files:
                file_path = file["filepath"]
                file_id = file["fileid"]

                download_path = os.path.join(dst_local_dir, file_path)
                await aiofiles.os.makedirs(os.path.dirname(download_path), exist_ok=True)

                async with aiofiles.open(download_path, "wb") as file:
                    req = drive_v3.files.get(
                        fileId=file_id, 
                        pipe_to=file, 
                        alt="media"
                    )
                    await self.send_req(aiogoogle, req)
            
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

gdapi = GDapi()

@tasks.loop(count=1, reconnect=False)
async def clean_GDrive() -> None:
    await gdapi.clear_drive()

@tasks.loop(hours=1, reconnect=False)
async def check_GDrive() -> None:
    if clean_GDrive.is_running():
        return

    cur_time = datetime.datetime.now()
    try:
        files = await gdapi.list_drive()
    except HTTPError as e:
        logger.error(f"GD-Error while listing drive (unexpected): {e}")
        print("Failed to check drive, check logs.")
        return

    for file in files:
        file_id = file["id"]

        created_time = parser.isoparse(file["createdTime"]) # RFC3339
        day_ahead = created_time + datetime.timedelta(days=1)

        if cur_time.date() >= day_ahead.date():
            try:
                await gdapi.delete_file(file_id)
            except HTTPError:
                pass