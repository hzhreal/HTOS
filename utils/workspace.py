import os
import sqlite3
import shutil
import aiosqlite
import discord
import aiofiles
import aiofiles.os
import aiohttp
from ftplib import FTP, error_perm
from aioftp.errors import AIOFTPException
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound, PSNAWPAuthenticationError
from network import FTPps
from utils.constants import (
    UPLOAD_DECRYPTED, UPLOAD_ENCRYPTED, DOWNLOAD_DECRYPTED, PNG_PATH, KEYSTONE_PATH, NPSSO_global,
    DOWNLOAD_ENCRYPTED, PARAM_PATH, STORED_SAVES_FOLDER, IP, PORT_FTP, MOUNT_LOCATION, PS_UPLOADDIR,
    DATABASENAME_THREADS, DATABASENAME_ACCIDS, DATABASENAME_BLACKLIST, BLACKLIST_MESSAGE, RANDOMSTRING_LENGTH, logger, blacklist_logger, psnawp,
    embChannelError, retry_emb, blacklist_emb
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

        #######
        conn = sqlite3.connect(DATABASENAME_BLACKLIST)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PS_Users (
                    account_id BLOB UNIQUE,
                    username TEXT UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Disc_Users (
                    user_id BLOB UNIQUE,
                    username TEXT UNIQUE
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
        await ctx.respond(embed=retry_emb)
        raise WorkspaceError("Please try again.")
    
    # check blacklist while we are at it
    if await blacklist_check_db(ctx.author.id, None):
        blacklist_logger.info(f"{ctx.author.name} ({ctx.author.id}) used a command while blacklisted!")
        await ctx.respond(embed=blacklist_emb)
        raise WorkspaceError(BLACKLIST_MESSAGE)

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

async def blacklist_write_db(disc_user: discord.User | None, account_id: str | None) -> None:
    """Add entry to the blacklist db."""
    if disc_user is None and account_id is None:
        return
    
    try:
        async with aiosqlite.connect(DATABASENAME_BLACKLIST) as db:
            cursor = await db.cursor()

            if disc_user is not None:
                userId = uint64(disc_user.id, "big")

                await cursor.execute("INSERT OR IGNORE INTO Disc_Users (user_id, username) VALUES (?, ?)", (userId.as_bytes, disc_user.name,))

            if account_id is not None:
                accid = int(account_id, 16)
                if NPSSO_global.val:
                    try:
                        ps_user = psnawp.user(account_id=str(accid))
                        username = ps_user.online_id
                    except PSNAWPNotFound:
                        username = None
                    except PSNAWPAuthenticationError:
                        username = None
                        NPSSO_global.val = ""
                accid = uint64(accid, "big")
                
                await cursor.execute("INSERT OR IGNORE INTO PS_Users (account_id, username) VALUES (?, ?)", (accid.as_bytes, username,))

            await db.commit()
    except aiosqlite.Error as e:
        blacklist_logger.error(f"Could not write to blacklist database: {e}")

async def blacklist_check_db(disc_userid: int | None, account_id: str | None) -> bool | None:
    """Check if value is blacklisted, only use argument, leave other to None."""
    if disc_userid is None and account_id is None:
        return # nothing provided
    elif disc_userid is not None and account_id is not None:
        return # invalid usage
    
    try:
        async with aiosqlite.connect(DATABASENAME_BLACKLIST) as db:
            cursor = await db.cursor()

            if disc_userid is not None:
                # userid provided
                val = uint64(disc_userid, "big")
                await cursor.execute("SELECT COUNT(*) FROM Disc_Users WHERE user_id = ?", (val.as_bytes,))
                res = await cursor.fetchone()
                if res[0] > 0:
                    return True

            else:
                # account_id provided
                val = int(account_id, 16)
                val = uint64(val, "big")
                await cursor.execute("SELECT COUNT(*) FROM PS_Users WHERE account_id = ?", (val.as_bytes,))
                res = await cursor.fetchone()
                if res[0] > 0:
                    return True
    except aiosqlite.Error as e:
        blacklist_logger.error(f"Could check blacklist database: {e}")

    return False

async def blacklist_del_db(disc_userid: int | None, account_id: str | None) -> None:
    """Delete entry in blacklist db."""
    if disc_userid is None and account_id is None:
        return
    
    try:
        async with aiosqlite.connect(DATABASENAME_BLACKLIST) as db:
            cursor = await db.cursor()

            if disc_userid is not None:
                # userid provided
                val = uint64(disc_userid, "big")
                await cursor.execute("DELETE FROM Disc_Users WHERE user_id = ?", (val.as_bytes,))

            else:
                # account_id provided
                val = int(account_id, 16)
                val = uint64(val, "big")
                await cursor.execute("DELETE FROM PS_Users WHERE account_id = ?", (val.as_bytes,))

            await db.commit()
    except aiosqlite.Error as e:
        blacklist_logger.error(f"Could not remove entry from blacklist database: {e}")

async def blacklist_delall_db() -> None:
    """Delete all entries in blacklist db."""
    try:
        async with aiosqlite.connect(DATABASENAME_BLACKLIST) as db:
            cursor = await db.cursor()

            await cursor.execute("DELETE FROM Disc_Users")
            await cursor.execute("DELETE FROM PS_Users")

            await db.commit()
    except aiosqlite.Error as e:
        blacklist_logger.error(f"Could not delete all entries in blacklist database: {e}")

async def blacklist_fetchall_db() -> dict[str, list[dict[str | None, str]] | list[dict[str | None, int]]]:
    """Obtain all entries inside the blacklist db."""
    entries = {"PlayStation account IDs": [], "Discord user IDs": []}

    accids = userids = []

    try:
        async with aiosqlite.connect(DATABASENAME_BLACKLIST) as db:
            cursor = await db.cursor()

            await cursor.execute("SELECT account_id, username FROM PS_Users")
            accids = await cursor.fetchall()

            await cursor.execute("SELECT user_id, username FROM Disc_Users")
            userids = await cursor.fetchall()
    except aiosqlite.Error as e:
        blacklist_logger.error(f"Could not fetch all blacklist database entries: {e}")

    for accid, username in accids:
        accid = uint64(accid, "big")

        entry = {username: hex(accid.value)}
        entries["PlayStation account IDs"].append(entry)

    for userid, username in userids:
        userid = uint64(userid, "big")

        entry = {username: userid.value}
        entries["Discord user IDs"].append(entry)
    return entries

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

# async def blacklist_parse(target_section: str, target_value: str) -> bool:
#     COMMENT_CHAR = "#"
#     SECTION_START = "["
#     SECTION_END = "]"

#     async with aiofiles.open(BLACKLIST_CONF_PATH) as conf:
#         section = ""
#         async for line in conf:
#             line = line.rstrip()

#             if not line or line.lstrip().startswith(COMMENT_CHAR):
#                 continue

#             if line.startswith(SECTION_START) and SECTION_END in line:
#                 section = line[line.find(SECTION_START) + 1 : line.find(SECTION_END)]
#                 continue

#             stripped_line = line.strip()
#             if stripped_line[:2].lower() == "0x":
#                 stripped_line = stripped_line[2:]

#             if section == target_section:
#                 if stripped_line.lower() == target_value.lower():
#                     return True
#     return False