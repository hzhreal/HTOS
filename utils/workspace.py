import os
import sqlite3
import time
import shutil
import aiosqlite
import discord
import aiofiles
import aiofiles.os
import aiohttp
from ftplib import FTP, error_perm
from aioftp.errors import AIOFTPException
from network import FTPps
from utils.constants import (
    UPLOAD_DECRYPTED, UPLOAD_ENCRYPTED, DOWNLOAD_DECRYPTED, PNG_PATH, KEYSTONE_PATH, 
    DOWNLOAD_ENCRYPTED, PARAM_PATH, STORED_SAVES_FOLDER, IP, PORT_FTP, MOUNT_LOCATION, PS_UPLOADDIR,
    DATABASENAME_THREADS, DATABASENAME_ACCIDS, RANDOMSTRING_LENGTH, logger, Color, Embed_t
)
from utils.extras import generate_random_string
from utils.type_helpers import uint64

class WorkspaceError(Exception):
    """Exception raised for errors to the workspace."""
    def __init__(self, message: str) -> None:
        self.message = message   

def delete_folder_contents_ftp_BLOCKING(ftp: FTP, folder_path: str) -> None:
    """Blocking FTP function to delete folders, used in startup to cleanup."""
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
                    logger.error(f"Permission error for {namew}: {e}")

        ftp.cwd("..")
        ftp.rmd(folder_path)
        logger.info(f"Folder contents of '{folder_path}' deleted successfully.")
    except error_perm as e:
        logger.error(f"An error occurred: {e}")

def startup():
    """Makes sure everything exists and cleans up unnecessary files, used when starting up bot."""
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
            ftp.connect(IP, PORT_FTP, timeout=10)
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
                    disc_userid BLOB,
                    disc_threadid BLOB
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
                    disc_userid BLOB,
                    ps_accountid BLOB
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(f"Error creating databases: {e}\nExiting...")
        logger.exception(f"Error creating databases: {e}")
        exit(-1)

async def cleanup(fInstance: FTPps, clean_list: list[str], saveList: list[str], mountPaths: list[str]) -> None:
    """Used to cleanup after a command utilizing the ps4 (remote)."""
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except OSError as e:
            logger.error(f"Error accessing {folderpath} when cleaning up: {e}")

    if mountPaths is not None and len(mountPaths) > 0:
        for mountlocation in mountPaths:
            await fInstance.delete_folder_contents_ftp(mountlocation)
        
    if saveList is not None and len(saveList) > 0:
        try:
            await fInstance.deleteList(PS_UPLOADDIR, saveList)
        except AIOFTPException as e:
            logger.error(f"An error occurred when cleaning up (FTP): {e}")

def cleanupSimple(clean_list: list[str]) -> None:
    """Used to cleanup after a command that does not utilize the ps4 (local only)."""
    for folderpath in clean_list:
        try:
            shutil.rmtree(folderpath)
        except OSError as e:
            logger.error(f"Error accessing {folderpath} when cleaning up (simple): {e}")

def initWorkspace() -> tuple[str, str, str, str, str, str, str]:
    """Obtains the local paths for an user, used when initializing a command that needs the local filesystem."""
    randomString = generate_random_string(RANDOMSTRING_LENGTH)
    newUPLOAD_ENCRYPTED = os.path.join(UPLOAD_ENCRYPTED, randomString)
    newUPLOAD_DECRYPTED = os.path.join(UPLOAD_DECRYPTED, randomString)
    newDOWNLOAD_ENCRYPTED = os.path.join(DOWNLOAD_ENCRYPTED, randomString)
    newPNG_PATH = os.path.join(PNG_PATH, randomString)
    newPARAM_PATH = os.path.join(PARAM_PATH, randomString)
    newDOWNLOAD_DECRYPTED = os.path.join(DOWNLOAD_DECRYPTED, randomString)
    newKEYSTONE_PATH = os.path.join(KEYSTONE_PATH, randomString)

    return newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH
    
async def makeWorkspace(ctx: discord.ApplicationContext, workspaceList: list[str], thread_id: int) -> None:
    """Used for checking if a command is being run in a valid thread."""
    embChannelError = discord.Embed(title="Error",
                                    description="Invalid channel!",
                                    colour=Color.DEFAULT.value)
    embChannelError.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

    threadId = uint64(thread_id, "big")

    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT * FROM Threads WHERE disc_threadid = ?", (threadId.as_bytes,))
            row = await cursor.fetchone()

            if row:
                for paths in workspaceList:
                    await aiofiles.os.makedirs(paths)
            else:
                await ctx.respond(embed=embChannelError)
                raise WorkspaceError("Invalid channel!")
    except aiosqlite.Error:
        raise WorkspaceError("Please try again.")

def enumerateFiles(fileList: list[str], randomString: str) -> list[str]:
    """Adds a random string at the end of the filename for save pairs, used to make sure there is no overwriting remotely."""
    for i, name in enumerate(fileList):
        if name.endswith("bin"):
            fileList[i] = os.path.splitext(os.path.basename(name))[0] + f"_{randomString}.bin" 
        else:
            fileList[i] = os.path.basename(name) + f"_{randomString}"

    return fileList

async def get_savename_from_bin_ext(path: str) -> str:
    savename = ""
    files = await aiofiles.os.listdir(path)
    
    for filename in files:
        name, ext = os.path.splitext(filename)
        if ext == ".bin":
            if name in files:
                savename = name
    return savename

async def listStoredSaves() -> dict[str, dict[str, dict[str, str]]]:
    """Lists the saves in the stored folder, used in the quick resign command."""
    gameList = await aiofiles.os.listdir(STORED_SAVES_FOLDER) 
    stored_saves = {}
       
    if len(gameList) == 0:
        raise WorkspaceError("NO STORED SAVES!")

    for game in gameList:
        gamePath = os.path.join(STORED_SAVES_FOLDER, game)

        if await aiofiles.os.path.isdir(gamePath):
            stored_saves[game] = {}

            gameRegions = await aiofiles.os.listdir(gamePath)

            for region in gameRegions:
                regionPath = os.path.join(STORED_SAVES_FOLDER, game, region)
                if await aiofiles.os.path.isdir(regionPath):
                    stored_saves[game][region] = {}
                    
                    gameSaves = await aiofiles.os.listdir(regionPath)
                    for save in gameSaves:
                        savePath = os.path.join(STORED_SAVES_FOLDER, game, region, save)
                        if await aiofiles.os.path.isdir(savePath):
                            if await get_savename_from_bin_ext(savePath):
                                stored_saves[game][region][save] = savePath
    
    return stored_saves
    
async def write_threadid_db(disc_userid: int, thread_id: int) -> list[int]:
    """Used to write thread IDs into the db on behalf of a user, if an entry exists it will be overwritten."""
    delete_these = []
    userId = uint64(disc_userid, "big")
    threadId = uint64(thread_id, "big")

    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT disc_threadid from Threads WHERE disc_userid = ?", (userId.as_bytes,)) # obtain thread id to delete from disc server, fetchall incase of any errors when deleting
            rows = await cursor.fetchall()
        
            await cursor.execute("DELETE FROM Threads WHERE disc_userid = ?", (userId.as_bytes,)) # delete all thread ids from a user in the database, limit to 1 thread per user
            await cursor.execute("INSERT INTO Threads (disc_userid, disc_threadid) VALUES (?, ?)", (userId.as_bytes, threadId.as_bytes,)) # finally, write
            await db.commit()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)
    
    for thread_id in rows:
        threadId = uint64(thread_id[0], "big")
        delete_these.append(threadId.value)
    return delete_these

async def fetchall_threadid_db() -> dict[int, int]:
    db_dict = {}
    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT disc_userid, disc_threadid FROM Threads")
            ids = await cursor.fetchall()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)

    for user_id, thread_id in ids:
        userId = uint64(user_id, "big")
        threadId = uint64(thread_id, "big")

        db_dict[userId.value] = threadId.value
    return db_dict

async def delall_threadid_db(db_dict: dict[int, int]) -> None:
    try:
        async with aiosqlite.connect(DATABASENAME_THREADS) as db:
            cursor = await db.cursor()

            for user_id, thread_id in db_dict.items():
                userId = uint64(user_id, "big")
                threadId = uint64(thread_id, "big")
                
                await cursor.execute("DELETE FROM Threads WHERE disc_userid = ? AND disc_threadid = ?", (userId.as_bytes, threadId.as_bytes,))
            await db.commit()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)
    
async def fetch_accountid_db(disc_userid: int) -> str | None:
    """Used to obtain an account ID stored in the db to user."""

    userId = uint64(disc_userid, "big")

    try:
        async with aiosqlite.connect(DATABASENAME_ACCIDS) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT ps_accountid FROM Account_IDs WHERE disc_userid = ?", (userId.as_bytes,))
            row = await cursor.fetchone()
    except aiosqlite.Error as e:
        raise WorkspaceError(e)
    
    if row:
        accid = uint64(row[0], "big")
        return accid.as_bytes.hex()
    else:
        return None
    
async def write_accountid_db(disc_userid: int, account_id: str) -> None:
    """Used to store the user's account ID in the db, removing the previously stored one."""
    
    accid = int(account_id, 16)
    accid = uint64(accid, "big")

    userId = uint64(disc_userid, "big")

    try:
        async with aiosqlite.connect(DATABASENAME_ACCIDS) as db:
            cursor = await db.cursor()

            await cursor.execute("DELETE FROM Account_IDs WHERE disc_userid = ?", (userId.as_bytes,)) # remove previously stored accid
            await cursor.execute("INSERT INTO Account_IDs (disc_userid, ps_accountid) VALUES (?, ?)", (userId.as_bytes, accid.as_bytes,))
            await db.commit()
    except aiosqlite.Error as e:
        logger.error(f"Could not write account ID to database: {e}")

def semver_to_num(ver: str | int) -> int:
    if isinstance(ver, int):
        return ver

    ver = ver[1:].split(".")
    ver = int("".join(ver))
    return ver

async def check_version() -> None:
    from utils.constants import VERSION

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.github.com/repos/hzhreal/HTOS/releases/latest") as resp:
            content = await resp.json()
            latest_ver = content.get("tag_name", 0)

    latest_ver_num = semver_to_num(latest_ver)
    cur_ver_num = semver_to_num(VERSION)
    
    if cur_ver_num < latest_ver_num:
        print("Attention: You are running an outdated version of HTOS. Please update to the latest version to ensure security, performance, and access to new features.")
        print(f"Your version: {VERSION}")
        print(f"Latest version: {latest_ver}")
        print("\n")
    elif cur_ver_num > latest_ver_num:
        print("Attention: You are running a version of HTOS that is newer than the latest release. Please report any bugs you may encounter.")
        print(f"Your version: {VERSION}")
        print(f"Latest version: {latest_ver}")
        print("\n")
    else:
        print("You are running the latest version of HTOS.")
        print(f"Your version: {VERSION}")
        print(f"Latest version: {latest_ver}")
        print("\n")