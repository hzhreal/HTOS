import os
import sqlite3
import time
import shutil
import asyncio
import aiosqlite
import discord
from ftplib import FTP, error_perm
from .constants import (UPLOAD_DECRYPTED, UPLOAD_ENCRYPTED, DOWNLOAD_DECRYPTED, PNG_PATH, KEYSTONE_PATH, 
                        DOWNLOAD_ENCRYPTED, PARAM_PATH, STORED_SAVES_FOLDER, IP, PORT, MOUNT_LOCATION, PS_UPLOADDIR,
                        DATABASENAME_THREADS, DATABASENAME_ACCIDS, RANDOMSTRING_LENGTH, OTHER_TIMEOUT, bot)
from .extras import generate_random_string
from aioftp.errors import AIOFTPException

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
    except error_perm as e:
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
    try:
        conn = sqlite3.connect(DATABASENAME_THREADS)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Threads (
                    disc_userid INTEGER,
                    disc_threadid INTEGER
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

        #######

        conn = sqlite3.connect(DATABASENAME_ACCIDS)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Account_IDs (
                    disc_userid INTEGER,
                    ps_accountid INTEGER
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error creating databases: {e}\nExiting...")
        exit(-1)

    time.sleep(1)
    os.system("cls" if os.name == "nt" else "clear")

async def cleanup(fInstance, clean_list: list, saveList: list, mountPaths: list) -> None:
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except OSError as e:
            print(f"Error accessing {folderpath} when cleaning up: {e}")

    if mountPaths is not None and len(mountPaths) > 0:
        for mountlocation in mountPaths:
            await fInstance.delete_folder_contents_ftp(mountlocation)
        
    if saveList is not None and len(saveList) > 0:
        try:
            await fInstance.deleteList(PS_UPLOADDIR, saveList)
        except AIOFTPException as e:
            print(f"An error occurred when cleaning up (FTP): {e}")

def cleanupSimple(clean_list: list) -> None:
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except OSError as e:
            print(f"Error accessing {folderpath} when cleaning up (simple): {e}")

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
    
async def makeWorkspace(ctx: discord.ApplicationContext, workspaceList: list, thread_id: int) -> None:
    embChannelError = discord.Embed(title="Error",
                                    description="Invalid channel!",
                                    colour=0x854bf7)
    embChannelError.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
    embChannelError.set_footer(text="Made with expertise by HTOP")

    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT * FROM Threads WHERE id = ?", (thread_id,))
            row = await cursor.fetchone()

            if row:
                for paths in workspaceList:
                    os.makedirs(paths)
            else:
                await ctx.respond(embed=embChannelError)
                raise WorkspaceError("Invalid channel!")
    except aiosqlite.Error:
        raise WorkspaceError("Please try again.")

def enumerateFiles(fileList: list, randomString: str) -> list:
    for i, name in enumerate(fileList):
        if name.endswith("bin"):
            fileList[i] = os.path.splitext(os.path.basename(name))[0] + f"_{randomString}.bin" 
        else:
            fileList[i] = os.path.basename(name) + f"_{randomString}"

    return fileList

async def listStoredSaves(ctx: discord.ApplicationContext) -> str | None:
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

    def check(message: discord.Message, ctx: discord.ApplicationContext, max_index: int) -> int | bool:
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
        message = await bot.wait_for("message", check=lambda message: check(message, ctx, len(save_paths)), timeout=OTHER_TIMEOUT) 
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
    
async def write_threadid_db(disc_userid: int, thread_id: int) -> list[int] | list:
    delete_these = []
    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT disc_threadid from Threads WHERE disc_userid = ?", (disc_userid,)) # obtain thread id to delete from disc server, fetchall incase of any errors when deleting
            rows = await cursor.fetchall()
        
            await cursor.execute("DELETE FROM Threads WHERE disc_userid = ?", (disc_userid,)) # delete all thread ids from a user in the database, limit to 1 thread per user
            await cursor.execute("INSERT INTO Threads (disc_userid, disc_threadid) VALUES (?, ?)", (disc_userid, thread_id,)) # finally, write
            await db.commit()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)
    
    for thread_id in rows:
        delete_these.append(thread_id[0])
    return delete_these

    
async def fetch_accountid_db(disc_userid: int) -> str | None:
    try:
        async with aiosqlite.connect(DATABASENAME_ACCIDS) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT ps_accountid FROM Account_IDs WHERE disc_userid = ?", (disc_userid,))
            row = await cursor.fetchone()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)
    
    if row:
        return row[0]
    else:
        return None
    
async def write_accountid_db(disc_userid: int, account_id: str) -> None:
    account_id = int(account_id, 16)
    try:
        async with aiosqlite.connect(DATABASENAME_ACCIDS) as db:
            cursor = await db.cursor()

            await cursor.execute("DELETE FROM Account_IDs WHERE disc_userid = ?", (disc_userid,)) # remove previously stored accid
            await cursor.execute("INSERT INTO Account_IDs (disc_userid, ps_accountid) VALUES (?, ?)", (disc_userid, account_id,))
            await db.commit()
    except aiosqlite.Error as e:
        print(f"Could not write account ID to database: {e}")
