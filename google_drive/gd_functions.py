import os
import discord
import asyncio
from dotenv import load_dotenv
from aiogoogle import Aiogoogle
import json
import aiofiles
import re
from utils.constants import SYS_FILE_MAX

load_dotenv()

class GDapiError(Exception):
    """Exception raised for errors related to the GDapi class."""
    def __init__(self, message: str) -> None:
        self.message = message

class GDapi:
    SAVEGAME_MAX = 1000 * 1024 * 1024 # # max for savegames 1000 MB
    credentials_path = str(os.getenv("GOOGLE_DRIVE_JSON_PATH"))

    creds = {
        "scopes": ["https://www.googleapis.com/auth/drive"],
        **json.load(open(credentials_path))
    }

    embednf = discord.Embed(title="Error: Google drive upload",
                        description="Could not locate any files inside your google drive folder. Are you sure I have permissions or that there is no folders inside?",
                        colour=0x854bf7)

    embednf.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
    embednf.set_footer(text="Made with expertise by HTOP")

    emblinkwrong = discord.Embed(title="Google drive upload: Error",
                      description="Could not obtain folder id from inputted link!",
                      colour=0x854bf7)
    emblinkwrong.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
    emblinkwrong.set_footer(text="Made with expertise by HTOP")
    
    @staticmethod
    async def grabfolderid(folder_link: str, ctx) -> str | bool:
        pattern = r"/folders/([\w-]+)" # regex pattern
        match = re.search(pattern, folder_link)

        if match:
            folder_id = match.group(1)
            print(f"The Folder ID is: {folder_id}")
            return folder_id
        else:
            print("Folder ID not found in the link.")
            await ctx.edit(embed=GDapi.emblinkwrong)
            return False

    @staticmethod
    def is_google_drive_link(text: str) -> bool:
        return bool(re.match(r"https://drive\.google\.com/.*", text))
    
    @staticmethod
    def fileCount(listedJSON: json) -> int:
        count = 0
        if listedJSON["files"]:
            for _ in listedJSON.get("files", []): 
                count += 1
        return count
    
    @staticmethod
    async def fileCheck(ctx, file_data: list, sys_files: list[str] | None, ps_save_pair_upload: bool) -> list:
        valid_files_data = []
        if ps_save_pair_upload:
            valid_files_data = await GDapi.save_pair_check(ctx, file_data)
            return valid_files_data
        
        for file_info in file_data:
            file_name = file_info["filename"]
            file_id = file_info["fileid"]
            file_size = file_info["filesize"]

            if file_size > GDapi.SAVEGAME_MAX:
                embFileLarge = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file size of '{file_name}' exceeds the limit of {int(GDapi.SAVEGAME_MAX / 1024 / 1024)} MB.",
                    colour=0x854bf7)
                embFileLarge.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                embFileLarge.set_footer(text="Made with expertise by HTOP")
                await ctx.edit(embed=embFileLarge)
                await asyncio.sleep(1)

            elif sys_files is not None and (file_size > SYS_FILE_MAX or file_name not in sys_files): # sce_sys files are not that big
                embnvSys = discord.Embed(title="Upload alert: Error",
                    description=f"{file_name} is not a valid sce_sys file!",
                    colour=0x854bf7)
                embnvSys.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                embnvSys.set_footer(text="Made with expertise by HTOP")
                await ctx.edit(embed=embnvSys)
                await asyncio.sleep(1)
            
            else:
                file_data = {"filename": file_name, "fileid": file_id}
                valid_files_data.append(file_data)
        return valid_files_data     

    @staticmethod
    async def save_pair_check(ctx, file_data: list) -> list:
        valid_saves_check1 = []
        for file_info in file_data:
            file_name = file_info["filename"]
            file_size = file_info["filesize"]
            file_id = file_info["fileid"]
            
            if file_name.endswith(".bin"):
                if file_size != 96:
                    embnvBin = discord.Embed(title="Upload alert: Error",
                        description=f"Sorry, the file size of '{file_name}' is not 96 bytes.",
                        colour=0x854bf7)
                    embnvBin.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                    embnvBin.set_footer(text="Made with expertise by HTOP")
                    await ctx.edit(embed=embnvBin)
                    await asyncio.sleep(1)

                else:
                    file_data = {"filename": file_name, "fileid": file_id}
                    valid_saves_check1.append(file_data)
            else:
                if file_size > GDapi.SAVEGAME_MAX:
                    embFileLarge = discord.Embed(title="Upload alert: Error",
                            description=f"Sorry, the file size of '{file_name}' exceeds the limit of {int(GDapi.SAVEGAME_MAX / 1024 / 1024)} MB.",
                            colour=0x854bf7)
                    embFileLarge.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                    embFileLarge.set_footer(text="Made with expertise by HTOP")
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
    async def uploadzip(cls, pathToFile: str, fileName: str) -> str | None:
        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")
            
            response = await aiogoogle.as_service_account(
                drive_v3.files.create(pipe_from=await aiofiles.open(pathToFile, "rb"), fields="id", json={"name": fileName})
            )

            await aiogoogle.as_service_account(
                drive_v3.permissions.create(fileId=response["id"], json={"role": "reader", "type": "anyone", "allowFileDiscovery": False})
            )
        file_url = f"https://drive.google.com/file/d/{response['id']}"
        
        return file_url

    @classmethod
    async def downloadsaves_gd(cls, ctx, folder_id: str, download_dir: str, max_files: int, sys_files: list[str, str, str, str , str] | None, ps_save_pair_upload: bool) -> list | str | None:
        uploaded_file_paths = []

        async with Aiogoogle(service_account_creds=cls.creds) as aiogoogle:
            drive_v3 = await aiogoogle.discover("drive", "v3")

            # List files in the folder
            listedJSON = await aiogoogle.as_service_account(
                drive_v3.files.list(q=f"'{folder_id}' in parents"),
            )

            count = GDapi.fileCount(listedJSON)
    
            if count <= max_files:
                file_data_storage = []

                for file_info in listedJSON.get("files", []):
                    file_name = file_info["name"]
                    file_id = file_info["id"]

                    file_size = await aiogoogle.as_service_account(
                            drive_v3.files.get(fileId=file_id, fields="size")
                        )
                    if file_size is None:
                        continue
                    file_size = int(file_size["size"])
                    
                    file_data = {"filename": file_name, "fileid": file_id, "filesize": file_size}
                    file_data_storage.append(file_data)

                valid_file_data = await GDapi.fileCheck(ctx, file_data_storage, sys_files, ps_save_pair_upload)
              
                for file_info in valid_file_data:
                    file_name = file_info["filename"]
                    file_id = file_info["fileid"]
                    
                    download_path = os.path.join(download_dir, file_name)
                    # Download the file
                    await aiogoogle.as_service_account(
                        drive_v3.files.get(fileId=file_id, pipe_to=await aiofiles.open(download_path, "wb"), alt="media")
                    )
                
                    uploaded_file_paths.append(file_name)
                    embeddone = discord.Embed(title="Google drive upload: Retrieved file",
                        description=f"{file_name} has been uploaded and saved.",
                        colour=0x854bf7)

                    embeddone.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")

                    embeddone.set_footer(text="Made with expertise by HTOP")
                    await ctx.edit(embed=embeddone)
                    
            else:
                print("Didnt find any files")
                await ctx.edit(embed=cls.embednf)
                await asyncio.sleep(0.5)
                raise GDapiError(f"G-D UPLOAD ERROR: No files found! Or they are more than {max_files}.")

        print("Download completed.")
        return uploaded_file_paths, file_name