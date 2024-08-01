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
from utils.constants import SYS_FILE_MAX, MAX_PATH_LEN, MAX_FILENAME_LEN, SEALED_KEY_ENC_SIZE, SAVESIZE_MAX, MOUNT_LOCATION, RANDOMSTRING_LENGTH, PS_UPLOADDIR, SCE_SYS_CONTENTS, logger, Color, Embed_t

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
    MAX_USER_NESTING = 100 # how deep a user can go when uploading files to create a save with
    credentials_path = str(os.getenv("GOOGLE_DRIVE_JSON_PATH"))

    creds = {
        "scopes": ["https://www.googleapis.com/auth/drive"],
        **json.load(open(credentials_path))
    }
    
    @staticmethod
    async def grabfolderid(folder_link: str, ctx: discord.ApplicationContext | discord.Message) -> str | bool:
        match = FOLDER_ID_RE.search(folder_link)

        if match:
            folder_id = match.group(1)
            return folder_id
        else:
            return False

    @staticmethod
    def is_google_drive_link(text: str) -> bool:
        return bool(GD_LINK_RE.match(text))
    
    @staticmethod
    def fileCount(listedJSON: json) -> int:
        count = 0
        if listedJSON["files"]:
            for _ in listedJSON.get("files", []): 
                count += 1
        return count
    
    @staticmethod
    def getErrStr_HTTPERROR(e: HTTPError) -> str:
        if e.res is None:
            return "HTTPError!"
        
        err = e.res.content.get("error")
        errCode = err.get("code")
        errMsg = []

        err_list = err.get("errors")       
        for error in err_list:
            errMsg.append(error.get("reason"))

        if len(errMsg) == 1:
            errMsg = errMsg[0]
        else:
            errMsg = ", ".join(errMsg)

        return f"HTTPERROR ({errCode}): {errMsg}."
    
    @staticmethod
    async def fileCheck(
              ctx: discord.ApplicationContext | discord.Message, 
              file_data: list[dict[str, str | int]], 
              sys_files: list[str] | None, 
              ps_save_pair_upload: bool, 
              ignore_filename_check: bool, 
              savesize: int | None = None
            ) -> list[dict[str, str]]:
        
        valid_files_data = []
        total_count = 0

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
                    description=f"Sorry, the file size of '{file_name}' exceeds the limit of {int(GDapi.SAVEGAME_MAX / 1024 / 1024)} MB.",
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

            elif savesize is not None and total_count > savesize:
                raise orbis.OrbisError(f"The files you are uploading for this save exceeds the savesize {savesize}!")
            
            else:
                total_count += file_size
                file_data = {"filename": file_name, "fileid": file_id}
                valid_files_data.append(file_data)
        return valid_files_data     

    @staticmethod
    async def save_pair_check(ctx: discord.ApplicationContext | discord.Message, file_data: list[dict[str, str | int]]) -> list[dict[str, str]]:
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
                    file_data = {"filename": file_name, "fileid": file_id}
                    valid_saves_check1.append(file_data)
            else:
                if file_size > GDapi.SAVEGAME_MAX:
                    embFileLarge = discord.Embed(
                        title="Upload alert: Error",
                        description=f"Sorry, the file size of '{file_name}' exceeds the limit of {int(GDapi.SAVEGAME_MAX / 1024 / 1024)} MB.",
                        colour=Color.DEFAULT.value
                    )
                    embFileLarge.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await ctx.edit(embed=embFileLarge)
                    await asyncio.sleep(1)
                else:
                    file_data = {"filename": file_name, "fileid": file_id}
                    valid_saves_check1.append(file_data)
        
        valid_saves_final = []
        for file_info in valid_saves_check1:
            file_name = file_info["filename"]
            file_id = file_info["fileid"]
            if file_name.endswith(".bin"): # look for corresponding file

                for file_info_nested in valid_saves_check1:
                    file_name_nested = file_info_nested["filename"]
                    file_id_nested = file_info_nested["fileid"]
                    if file_name_nested == file_name: continue

                    elif file_name_nested == os.path.splitext(file_name)[0]:
                        file_data = {"filename": file_name, "fileid": file_id}
                        valid_saves_final.append(file_data)
                        file_data = {"filename": file_name_nested, "fileid": file_id_nested}
                        valid_saves_final.append(file_data)
                        break
                        
        return valid_saves_final
    
    @classmethod
    async def list_dir(
              cls, 
              ctx: discord.ApplicationContext | discord.Message, 
              folder_id: str, 
              max_files: int, 
              cur_nesting: int = 0, 
              rel_path: str | None = None, 
              files: list[dict[str, str]] | None = None
            ) -> list[dict[str, str]]:
    
        async def warn_pathlen(path: str, real_len: int, lim: int) -> None:
            embpl = discord.Embed(
                title="Upload alert: Error",
                description=f"Sorry, the path '{path}' ({real_len}) exceeds {lim}.",
                colour=Color.DEFAULT.value
            )
            embpl.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embpl)
            await asyncio.sleep(1)

        async def warn_filelen(filename: str, lim: int) -> None:
            embfn = discord.Embed(
                title="Upload alert: Error",
                description=f"Sorry, the file name of '{filename}' ({len(filename)}) exceeds {lim}.",
                colour=Color.DEFAULT.value
            )
            embfn.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embfn)
            await asyncio.sleep(1)

        if files is None:
            files = []

        if cur_nesting > cls.MAX_USER_NESTING:
            raise GDapiError(f"Max level nesting of {cls.MAX_USER_NESTING} reached!")

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            # List files in the folder
            listedJSON = await aiogoogle.as_service_account(
                drive_v3.files.list(
                    q=f"'{folder_id}' in parents and trashed=false", 
                    fields="files(name, id, size, mimeType)")
            )

            count = GDapi.fileCount(listedJSON)
    
            if count <= max_files:
                file_data_storage = []

                for file_info in listedJSON.get("files", []):
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
                            path_len = len(MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + rel_path + "/")
                            if path_len > MAX_PATH_LEN:
                                await warn_pathlen(rel_path, path_len, MAX_PATH_LEN)
                                continue
                        else:
                            rel_path = file_name
                        await cls.list_dir(ctx, file_id, max_files, cur_nesting + 1, rel_path, files)
                        # go up one level
                        rel_path = os.path.dirname(rel_path)
                    else:
                        if file_size == 0 or file_name in SCE_SYS_CONTENTS:
                            continue
                        
                        if rel_path is not None:
                            file_path = os.path.join(rel_path, file_name)
                            file_path = os.path.normpath(file_path)
                            path_len = len(MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + file_path + "/")
                            if len(file_name) > MAX_FILENAME_LEN:
                                await warn_filelen(file_name, MAX_FILENAME_LEN)
                                continue
                            elif path_len > MAX_PATH_LEN:
                                await warn_pathlen(rel_path, path_len, MAX_PATH_LEN)
                                continue
                        else:
                            file_path = file_name
                    
                        file_data = {"filename": file_path, "fileid": file_id, "filesize": file_size}
                        file_data_storage.append(file_data)

                valid_file_data = await GDapi.fileCheck(ctx, file_data_storage, None, False, True)
                for data in valid_file_data:
                    file_path = data["filename"]
                    file_id = data["fileid"]

                    file_data = {"filepath": file_path, "fileid": file_id, "filesize": file_size} 
                    files.append(file_data)

                return files

            else:
                raise GDapiError(f"G-D UPLOAD ERROR: No files found! Or they are more than {max_files}.")

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
    async def uploadzip(cls, pathToFile: str, fileName: str) -> str:
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            
            try:
                response = await aiogoogle.as_service_account(
                    drive_v3.files.create(
                        pipe_from=await aiofiles.open(pathToFile, "rb"), 
                        fields="id", json={"name": fileName})
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
    async def downloadsaves_gd(
              cls, 
              ctx: discord.ApplicationContext | discord.Message, 
              folder_id: str, 
              download_dir: str, 
              max_files: int, 
              sys_files: list[str] | None, 
              ps_save_pair_upload: bool, 
              ignore_filename_check: bool,
              savesize: int | None = None
            ) -> list[str]:
        
        uploaded_file_paths = []

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            # List files in the folder
            listedJSON = await aiogoogle.as_service_account(
                drive_v3.files.list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields="files(name, id, size)")
            )

            count = GDapi.fileCount(listedJSON)
    
            if count <= max_files and count >= 1:
                file_data_storage = []

                for file_info in listedJSON.get("files", []):
                    file_name = file_info["name"]
                    file_id = file_info["id"]
                    file_size = int(file_info.get("size", 0))

                    if file_size == 0:
                        continue
                    
                    file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                    file_data_storage.append(file_data)

                valid_file_data = await GDapi.fileCheck(ctx, file_data_storage, sys_files, ps_save_pair_upload, ignore_filename_check, savesize)

                for file_info in valid_file_data:
                    file_name = file_info["filename"]
                    file_id = file_info["fileid"]
                    
                    download_path = os.path.join(download_dir, file_name)
                    # Download the file
                    await aiogoogle.as_service_account(
                        drive_v3.files.get(fileId=file_id, pipe_to=await aiofiles.open(download_path, "wb"), alt="media")
                    )
                
                    uploaded_file_paths.append(download_path)

                    logger.info(f"Saved {file_name} to {download_path}")
                    embeddone = discord.Embed(
                        title="Google drive upload: Retrieved file",
                        description=f"{file_name} has been uploaded and saved.",
                        colour=Color.DEFAULT.value
                    )
                    embeddone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await ctx.edit(embed=embeddone)
                    
            else:
                raise GDapiError(f"G-D UPLOAD ERROR: No files found! Or they are more than {max_files}.")
            
        return uploaded_file_paths
    
    @classmethod
    async def downloadfiles_recursive(cls, ctx: discord.ApplicationContext | discord.Message, dst_local_dir: str, folder_id: str, max_files_in_dir: int, savesize: int | None = None) -> list[str]:
        files = await cls.list_dir(ctx, folder_id, max_files_in_dir)
        uploaded_file_paths = []
        if len(files) == 0:
            return uploaded_file_paths
        total_count = 0

        for entry in files:
            file_size = entry["filesize"]
            total_count += file_size

        if savesize is not None and total_count > savesize:
            raise orbis.OrbisError(f"The files you are uploading for this save exceeds the savesize {savesize}!")

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

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
                    description=f"{file_path} has been uploaded and saved.",
                    colour=Color.DEFAULT.value
                )
                embeddone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                await ctx.edit(embed=embeddone)
            
            return uploaded_file_paths
