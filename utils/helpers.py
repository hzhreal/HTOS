import discord
import asyncio
import os
import re
import json
import aiohttp
import data.crypto.helpers as crypthelp
import utils.orbis as orbis
import aiofiles.os
from discord.ui.item import Item
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound
from google_drive import GDapi, GDapiError
# from data.crypto.helpers import extra_import
from network import FTPps
# from utils.orbis import checkSaves, handle_accid, checkid
from utils.constants import (
    logger, Color, bot, psnawp, 
    NPSSO, UPLOAD_TIMEOUT, FILE_LIMIT_DISCORD, SCE_SYS_CONTENTS, OTHER_TIMEOUT, MAX_FILES, BOT_DISCORD_UPLOAD_LIMIT,
    embgdt, embUtimeout, embnt, embnv1, emb8, embvalidpsn
)
from utils.exceptions import PSNIDError, FileError
from utils.workspace import fetch_accountid_db, write_accountid_db, cleanup, cleanupSimple, write_threadid_db, WorkspaceError
from utils.extras import zipfiles

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
    
    async def handle_timeout(self, ctx: discord.ApplicationContext) -> None:
        await asyncio.sleep(2)
        if not self.done:
            await ctx.edit(embed=self.embTimeout, view=None)
            await asyncio.sleep(4) # make sure user is aware of msg
            self.done = True

class threadButton(discord.ui.View):
    """The panel that allows the user to create a thread to use the bot."""
    def __init__(self) -> None:
        super().__init__(timeout=None)


    async def on_error(self, _: Exception, __: Item, ___: discord.Interaction) -> None:
        pass
    
    @discord.ui.button(label="Create thread", style=discord.ButtonStyle.primary, custom_id="CreateThread")
    async def callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Creating thread...", ephemeral=True)

        ids_to_remove = []
        
        try:
            thread = await interaction.channel.create_thread(name=interaction.user.name, auto_archive_duration=10080)
            await thread.send(interaction.user.mention)
            ids_to_remove = await write_threadid_db(interaction.user.id, thread.id)
            
        except (WorkspaceError, discord.Forbidden) as e:
            logger.error(f"Can not create thread: {e}")
        
        try:
            for thread_id in ids_to_remove:
                old_thread = bot.get_channel(thread_id)
                if old_thread is not None:
                    await old_thread.delete() 
        except discord.Forbidden:
            pass


async def errorHandling(ctx: discord.ApplicationContext, error: str, workspaceFolders: list[str], uploaded_file_paths: list[str], mountPaths: list[str], C1ftp: FTPps) -> None:
    embe = discord.Embed(title="Error",
                            description=error,
                    colour=Color.DEFAULT.value)
    embe.set_footer(text="Made by hzh.")
    await ctx.edit(embed=embe)
    if C1ftp is not None:
        await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)
    else:
        cleanupSimple(workspaceFolders)

async def upload2(ctx: discord.ApplicationContext, saveLocation: str, max_files: int, sys_files: bool, ps_save_pair_upload: bool) -> list | None:
    """Makes the bot expect multiple files through discord or google drive."""
    def check(message: discord.Message, ctx: discord.ApplicationContext) -> discord.Attachment | str:
        if message.author == ctx.author and message.channel == ctx.channel:
            return len(message.attachments) >= 1 or (message.content and GDapi.is_google_drive_link(message.content))

    try:
        message = await bot.wait_for("message", check=lambda message: check(message, ctx), timeout=UPLOAD_TIMEOUT)  # Wait for 300 seconds for a response with one attachments
    except asyncio.TimeoutError:
        await ctx.edit(embed=embUtimeout)
        raise TimeoutError("TIMED OUT!")

    if len(message.attachments) >= 1 and len(message.attachments) <= max_files:
        attachments = message.attachments
        uploaded_file_paths = []
        await message.delete()
        valid_attachments = await orbis.checkSaves(ctx, attachments, ps_save_pair_upload, sys_files)

        for attachment in valid_attachments:
            file_path = os.path.join(saveLocation, attachment.filename)
            await attachment.save(file_path)
            
            emb1 = discord.Embed(title="Upload alert: Successful", 
                                 description=f"File '{attachment.filename}' has been successfully uploaded and saved.", 
                                 colour=Color.DEFAULT.value)
            emb1.set_footer(text="Made by hzh.")

            logger.info(f"Saved {attachment.filename} to {file_path}")
            
            await ctx.edit(embed=emb1)
            uploaded_file_paths.append(file_path)
    
    elif message.content != None:
        try:
            google_drive_link = message.content
            await message.delete()
            folder_id = await GDapi.grabfolderid(google_drive_link, ctx)
            if not folder_id: raise GDapiError("Could not find the folder id!")
            uploaded_file_paths, *_ = await GDapi.downloadsaves_gd(ctx, folder_id, saveLocation, max_files, [SCE_SYS_CONTENTS] if sys_files else None, ps_save_pair_upload)
           
        except asyncio.TimeoutError:
            await ctx.edit(embed=embgdt)
            raise TimeoutError("TIMED OUT!")
    
    else:
        await ctx.send("Reply to the message with files that does not reach the limit, or a public google drive link (no subfolders and dont reach the file limit)!", ephemeral=True)
        
    return uploaded_file_paths

async def upload1(ctx: discord.ApplicationContext, saveLocation: str) -> str | None:
    """Makes the bot expect a single file through discord or google drive."""
    def check(message: discord.Message, ctx: discord.ApplicationContext) -> discord.Attachment | str:
        if message.author == ctx.author and message.channel == ctx.channel:
            return len(message.attachments) == 1 or (message.content and GDapi.is_google_drive_link(message.content))
        
    try:
        message = await bot.wait_for("message", check=lambda message: check(message, ctx), timeout=UPLOAD_TIMEOUT)  # Wait for 120 seconds for a response with an attachment
    except asyncio.TimeoutError:
        await ctx.edit(embed=embUtimeout)
        raise TimeoutError("TIMED OUT!")

    if len(message.attachments) == 1:
        attachment = message.attachments[0]

        if attachment.size > FILE_LIMIT_DISCORD:
            emb15 = discord.Embed(title="Upload alert: Error",
                      description=f"Sorry, the file size of '{attachment.filename}' exceeds the limit of {int(FILE_LIMIT_DISCORD / 1024 / 1024)} MB.",
                      colour=Color.DEFAULT.value)
            emb15.set_footer(text="Made by hzh.")

            await ctx.edit(embed=emb15)
            await message.delete()
            raise FileError("DISCORD UPLOAD ERROR: File size too large!")
        
        else:
            save_path = saveLocation
            file_path = os.path.join(save_path, attachment.filename)
            await attachment.save(file_path)
            logger.info(f"Saved {attachment.filename} to {file_path}")
            emb16 = discord.Embed(title="Upload alert: Successful", 
                                  description=f"File '{attachment.filename}' has been successfully uploaded and saved.", 
                                  colour=Color.DEFAULT.value)
            emb16.set_footer(text="Made by hzh.")
            await message.delete()
            await ctx.edit(embed=emb16)

            name_of_file = attachment.filename

    elif message.content != None:
        try:
            google_drive_link = message.content
            await message.delete()
            folder_id = await GDapi.grabfolderid(google_drive_link, ctx)
            if not folder_id: raise GDapiError("Could not find the folder id!")
            *_ , name_of_file = await GDapi.downloadsaves_gd(ctx, folder_id, saveLocation, max_files=1, sys_files=False, ps_save_pair_upload=False)

        except asyncio.TimeoutError:
            await ctx.edit(embed=embgdt)
            raise TimeoutError("TIMED OUT!")
    
    else:
        await ctx.send("Reply to the message with either 1 file, or a public google drive folder link (no subfolders and dont reach the file limit)!", ephemeral=True)

    return name_of_file
    
async def psusername(ctx: discord.ApplicationContext, username: str) -> str | None:
    """Used to obtain an account ID, either through converting from username, obtaining from db, or manually. Utilizes the PSN API or a website doing it for us."""
    await ctx.defer()

    if username == "":
        user_id = await fetch_accountid_db(ctx.author.id)
        if user_id is not None:
            user_id = hex(user_id)[2:]
            return user_id
        else:
            raise PSNIDError("Could not find previously stored account ID.")

    def check(message: discord.Message, ctx: discord.ApplicationContext) -> str:
        if message.author == ctx.author and message.channel == ctx.channel:
            return message.content and orbis.checkid(message.content)

    limit = 0
    usernamePattern = r"^[a-zA-Z0-9_-]+$"

    if len(username) < 3 or len(username) > 16:
        await ctx.edit(embed=embnv1)
        raise PSNIDError("Invalid PS username!")
    elif not bool(re.match(usernamePattern, username)):
        await ctx.edit(embed=embnv1)
        raise PSNIDError("Invalid PS username!")

    if NPSSO is not None:
        try:
            userSearch = psnawp.user(online_id=username)
            user_id = userSearch.account_id
            user_id = orbis.handle_accid(user_id)
            delmsg = False
        
        except PSNAWPNotFound:
            await ctx.respond(embed=emb8)
            delmsg = True

            try:
                response = await bot.wait_for("message", check=lambda message: check(message, ctx), timeout=OTHER_TIMEOUT)
                user_id = response.content
                await response.delete()
            except asyncio.TimeoutError:
                await ctx.edit(embed=embnt)
                raise TimeoutError("TIMED OUT!")
    else:
        while True:

            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://psn.flipscreen.games/search.php?username={username}") as response:
                    response.text = await response.text()

            if response.status == 200 and limit != 20:
                data = json.loads(response.text)
                obtainedUsername = data["online_id"]

                if obtainedUsername.lower() == username.lower():
                    user_id = data["user_id"]
                    user_id = orbis.handle_accid(user_id)
                    delmsg = False
                    break
                else:
                    limit += 1
            else:
                await ctx.respond(embed=emb8)
                delmsg = True

                try:
                    response = await bot.wait_for("message", check=lambda message: check(message, ctx), timeout=OTHER_TIMEOUT)
                    user_id = response.content
                    await response.delete()
                    break
                except asyncio.TimeoutError:
                    await ctx.edit(embed=embnt)
                    raise TimeoutError("TIMED OUT!")
            
    if delmsg:
        await asyncio.sleep(0.5)
        await ctx.edit(embed=embvalidpsn)
    else:
        await ctx.respond(embed=embvalidpsn)

    await asyncio.sleep(0.5)
    await write_accountid_db(ctx.author.id, user_id.lower())
    return user_id.lower()

async def replaceDecrypted(ctx: discord.ApplicationContext, fInstance: FTPps, files: list[str], titleid: str, mountLocation: str , upload_individually: bool, upload_decrypted: str, savePairName: str) -> list[str] | None:
    """Used in the encrypt command to replace files one by one, or how many you want at once."""
    from utils.namespaces import Crypto
    completed = []
    if upload_individually or len(files) == 1:
        for file in files:
            fullPath = mountLocation + "/" + file
            cwdHere = fullPath.split("/")
            lastN = cwdHere.pop(len(cwdHere) - 1)
            cwdHere = "/".join(cwdHere)

            emb18 = discord.Embed(title=f"Resigning Process (Decrypted): Upload\n{savePairName}",
                            description=f"Please attach a decrypted savefile that you want to upload, MUST be equivalent to {file} (can be any name).",
                            colour=Color.DEFAULT.value)
            emb18.set_footer(text="Made by hzh.")

            await ctx.edit(embed=emb18)

            attachmentName = await upload1(ctx, upload_decrypted)
            attachmentPath = os.path.join(upload_decrypted, attachmentName)
            newPath = os.path.join(upload_decrypted, lastN)
            await aiofiles.os.rename(attachmentPath, newPath)
            await crypthelp.extra_import(Crypto, titleid, newPath)

            await fInstance.replacer(cwdHere, lastN)
            completed.append(file)
    
    else:
        SPLITVALUE = "SLASH"
        patterned = "\n".join(files)
        emb18 = discord.Embed(title=f"Resigning Process (Decrypted): Upload\n{savePairName}",
                            description=f"Please attach at least one of these files and make sure its the same name, including path in the name if that is the case. Instead of '/' use '{SPLITVALUE}', here are the contents:\n\n**{patterned}**",
                            colour=Color.DEFAULT.value)
        emb18.set_footer(text="Made by hzh.")

        await ctx.edit(embed=emb18)
        uploaded_file_paths = await upload2(ctx, upload_decrypted, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=False)

        if len(uploaded_file_paths) >= 1:
            for file in await aiofiles.os.listdir(upload_decrypted):
                file1 = file.split(SPLITVALUE)
                if file1[0] == "": file1 = file1[1:]
                file1 = "/".join(file1)

                if file1 not in patterned:
                    await aiofiles.os.remove(os.path.join(upload_decrypted, file))
                    
                else:
                    for saveFile in files:
                        if file1 == saveFile:
                            lastN = os.path.basename(saveFile)
                            cwdHere = saveFile.split("/")
                            cwdHere = cwdHere[:-1]
                            cwdHere = "/".join(cwdHere)
                            cwdHere = mountLocation + "/" + cwdHere

                            filePath = os.path.join(upload_decrypted, file)
                            newRename = os.path.join(upload_decrypted, lastN)
                            await aiofiles.os.rename(filePath, newRename)
                            await crypthelp.extra_import(Crypto, titleid, newRename)

                            await fInstance.replacer(cwdHere, lastN) 
                            completed.append(lastN)     
                    
        else:
            raise FileError("Too many files!")

    if len(completed) == 0:
        raise FileError("Could not replace any files")

    return completed

async def send_final(ctx: discord.ApplicationContext, file_name: str, zipupPath: str) -> None:
    """Zips path and uploads file through discord or google drive depending on the size."""
    zipfiles(zipupPath, file_name)
    final_file = os.path.join(zipupPath, file_name)
    final_size = await aiofiles.os.path.getsize(final_file)
    file_size_mb = final_size / (1024 * 1024)

    if file_size_mb < BOT_DISCORD_UPLOAD_LIMIT:
        await ctx.respond(file=discord.File(final_file))
    else:
        file_url = await GDapi.uploadzip(final_file, file_name)
        embg = discord.Embed(title="Google Drive: Upload complete",
                    description=file_url,
                    colour=Color.DEFAULT.value)
        embg.set_footer(text="Made by hzh.")
        await ctx.respond(embed=embg)