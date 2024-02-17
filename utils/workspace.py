import os
from ftplib import FTP, error_perm
from .constants import (UPLOAD_DECRYPTED, UPLOAD_ENCRYPTED, DOWNLOAD_DECRYPTED, PNG_PATH, KEYSTONE_PATH, 
                        DOWNLOAD_ENCRYPTED, PARAM_PATH, STORED_SAVES_FOLDER, IP, PORT, MOUNT_LOCATION, PS_UPLOADDIR,
                        DATABASENAME, RANDOMSTRING_LENGTH, UPLOAD_TIMEOUT, bot)
from .extras import generate_random_string
import sqlite3
import time
import shutil
import asyncio
import aiosqlite
import discord

class WorkspaceError(Exception):
    """Exception raised for errors to the workspace."""
    def __init__(self, message: str) -> None:
        self.message = message    

def delete_folder_contents_ftp_BLOCKING(ftp: FTP, folder_path: str) -> None:
    try:
        ftp.cwd(folder_path)
        items9 = ftp.mlsd()

        for namew, attrs in items9:
            if namew in [".", ".."]:
                continue

            if attrs["type"] == "dir":
                delete_folder_contents_ftp_BLOCKING(ftp, namew)
            else:
                try:
                    ftp.delete(namew)
                except error_perm as e:
                    print(f"Permission error for {namew}: {e}")

        ftp.cwd("..")
        ftp.rmd(folder_path)
        print(f"Folder contents of '{folder_path}' deleted successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

def startup():
    FOLDERS = [UPLOAD_ENCRYPTED, UPLOAD_DECRYPTED, 
                DOWNLOAD_ENCRYPTED, DOWNLOAD_DECRYPTED,
                PNG_PATH, PARAM_PATH, KEYSTONE_PATH, STORED_SAVES_FOLDER]
    
    for path in FOLDERS:
        if not os.path.exists(path):
            try: os.makedirs(path)
            except:
                print(f"Can not create essential folders, make sure they are created!\n{', '.join(FOLDERS)}")
                exit()
        else:
            if path != STORED_SAVES_FOLDER:
                shutil.rmtree(path)

                try: os.makedirs(path)
                except:
                    print(f"Can not create essential folders, make sure they are created!\n{', '.join(FOLDERS)}")
                    exit()

    with FTP() as ftp:
        try:
            ftp.connect(IP, PORT)
            login_result = ftp.login()  # Call the login method and get its return value
            if login_result == "230 User logged in, proceed.":
                try:
                    ftp.mkd(MOUNT_LOCATION)
                    ftp.mkd(PS_UPLOADDIR)
                except: pass
                delete_folder_contents_ftp_BLOCKING(ftp, MOUNT_LOCATION)
                delete_folder_contents_ftp_BLOCKING(ftp, PS_UPLOADDIR)
                ftp.mkd(MOUNT_LOCATION)
                ftp.mkd(PS_UPLOADDIR) 
                ftp.quit()
        except:
            pass

    conn = sqlite3.connect(DATABASENAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Threads (
                   id INTEGER
        )
    """)
    conn.commit()
    conn.close()

    time.sleep(1)
    os.system("cls" if os.name == "nt" else "clear")

async def cleanup(fInstance, clean_list: list, saveList: list, mountPaths: list) -> None:
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except Exception as e:
            print(f"Error accessing {folderpath}: {e}")

    if mountPaths is not None and len(mountPaths) > 0:
        for mountlocation in mountPaths:
            await fInstance.delete_folder_contents_ftp(mountlocation)
        
    if saveList is not None and len(saveList) > 0:
        try:
            await fInstance.deleteList(PS_UPLOADDIR, saveList)
        except Exception as e:
            print(f"An error occurred: {e}")

def cleanupSimple(clean_list: list) -> None:
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except Exception as e:
            print(f"Error accessing {folderpath}: {e}")

def initWorkspace() -> tuple[str, str, str, str, str, str, str]:
    randomString = generate_random_string(RANDOMSTRING_LENGTH)
    newUPLOAD_ENCRYPTED = os.path.join(UPLOAD_ENCRYPTED, randomString)
    newUPLOAD_DECRYPTED = os.path.join(UPLOAD_DECRYPTED, randomString)
    newDOWNLOAD_ENCRYPTED = os.path.join(DOWNLOAD_ENCRYPTED, randomString)
    newPNG_PATH = os.path.join(PNG_PATH, randomString)
    newPARAM_PATH = os.path.join(PARAM_PATH, randomString)
    newDOWNLOAD_DECRYPTED = os.path.join(DOWNLOAD_DECRYPTED, randomString)
    newKEYSTONE_PATH = os.path.join(KEYSTONE_PATH, randomString)

    return newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH
    
async def makeWorkspace(ctx, workspaceList: list) -> None:
    embChannelError = discord.Embed(title="Error",
                                    description="Invalid channel!",
                                    colour=0x854bf7)
    embChannelError.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
    embChannelError.set_footer(text="Made with expertise by HTOP")


    async with aiosqlite.connect(DATABASENAME) as db:
        cursor = await db.cursor()
        await cursor.execute("SELECT * FROM Threads")
        rows = await cursor.fetchall()

        if any(ctx.channel.id == row[0] for row in rows):
            for paths in workspaceList:
                os.makedirs(paths)
        else:
            await ctx.respond(embed=embChannelError)
            raise WorkspaceError("Invalid channel!")

def enumerateFiles(fileList: list, randomString: str) -> list:
    for i, name in enumerate(fileList):
        if name.endswith("bin"):
            fileList[i] = os.path.splitext(os.path.basename(name))[0] + f"_{randomString}.bin" 
        else:
            fileList[i] = os.path.basename(name) + f"_{randomString}"

    return fileList

async def listStoredSaves(ctx) -> str | None:
    gameList = os.listdir(STORED_SAVES_FOLDER)
    description = ""
    save_paths = []
    index = 1
            
    if len(gameList) == 0:
        raise WorkspaceError("NO STORED SAVES!")
    
    for game in gameList:
        gamePath = os.path.join(STORED_SAVES_FOLDER, game)

        if os.path.isdir(gamePath):
            description += f"**{game}**\n"

            gameRegions = os.listdir(gamePath)

            for region in gameRegions:
                regionPath = os.path.join(STORED_SAVES_FOLDER, game, region)
                if os.path.isdir(regionPath):
                    description += f"- {region}\n"
                    
                    gameSaves = os.listdir(regionPath)
                    for save in gameSaves:
                        savePath = os.path.join(STORED_SAVES_FOLDER, game, region, save)
                        if os.path.isdir(savePath):
                            description += f"-- {index}. {save}\n"
                            save_paths.append(savePath)
                            index += 1

    embList = discord.Embed(title="List of available saves",
                        description=f"{description}\nType in the number associated to the save to resign it, or send 'EXIT' to cancel.",
                        colour=0x854bf7)
    embList.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
    embList.set_footer(text="Made with expertise by HTOP")

    await ctx.edit(embed=embList)

    def check(message, ctx, max_index: int) -> int | bool:
        if message.author == ctx.author and message.channel == ctx.channel:
            if message.content == "EXIT":
                return message.content
            else:
                try:
                    index = int(message.content)
                    return 1 <= index <= max_index
                except ValueError:
                    return False
        return False
        
    try:
        message = await bot.wait_for('message', check=lambda message: check(message, ctx, len(save_paths)), timeout=UPLOAD_TIMEOUT) 
    except asyncio.TimeoutError:
        raise TimeoutError("TIMED OUT!")
    
    await message.delete()
    
    if message.content == "EXIT":
        return message.content
    
    else:
        selected_save = save_paths[int(message.content) - 1]
        saves = os.listdir(selected_save)

        for save in saves:
            if not save.endswith(".bin"):
                selected_save = os.path.join(selected_save, save)

        return selected_save
