import aiofiles.ospath
import discord
import asyncio
import os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import gdapi, GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, SHARED_GD_LINK_DESC, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    ICON0_FORMAT, ICON0_MAXSIZE, ICON0_NAME, COMMAND_COOLDOWN,
    logger, Color, Embed_t,
    embpng, embTitleChange, embTitleErr
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple
from utils.extras import pngprocess
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, send_final
from utils.orbis import handleTitles, SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, OrbisError, WorkspaceError
from utils.instance_lock import INSTANCE_LOCK_global

class Change(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    change_group = discord.SlashCommandGroup("change")
    
    @change_group.command(description="Changes the picture of your save, this is just cosmetic.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def picture(
              self, 
              ctx: discord.ApplicationContext, 
              picture: discord.Attachment, 
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:
        
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORT_CECIE)
        mountPaths = []
        pngfile = os.path.join(newPNG_PATH, ICON0_NAME)

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=embpng)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)

            # png handling
            await picture.save(pngfile)
            pngprocess(pngfile, ICON0_FORMAT)
            png_size = await aiofiles.ospath.getsize(pngfile)
            if png_size > ICON0_MAXSIZE:
                raise FileError(f"Image turned out to be too big: {png_size}/{ICON0_MAXSIZE}!")
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
                
        batches = len(uploaded_file_paths)
        batch = SaveBatch(C1ftp, C1socket, user_id, [], mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)

        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError as e:
                await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return
            
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()

                    embpng1 = discord.Embed(
                        title="PNG process: Initializng",
                        description=f"Your save (**{savefile.basename}**) is being mounted, (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    embpng1.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embpng1)

                    await savefile.dump()

                    embpng2 = discord.Embed(
                        title="PNG process: Initializng",
                        description=f"Your save (**{savefile.basename}**) has mounted, (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    embpng2.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embpng2)

                    await C1ftp.swappng(batch.location_to_scesys)
                    await savefile.resign()

                    embpngs = discord.Embed(
                        title="PNG process: Successful",
                        description=f"Altered the save png and resigned **{savefile.basename}** (save {j}/{batch.savecount}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    embpngs.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embpngs)
                    j += 1

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            embPdone = discord.Embed(
                title="PNG process: Successful",
                description=f"Altered the save png of **{batch.printed}** and resigned to **{playstation_id or user_id}** (batch {i}/{batches}).",
                colour=Color.DEFAULT.value
            )
            embPdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embPdone)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException) as e:
                await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return
            
            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

    @change_group.command(description="Change the titles of your save.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def title(
              self, 
              ctx: discord.ApplicationContext, 
              maintitle: Option(str, description="For example Grand Theft Auto V.", default=""), # type: ignore
              subtitle: Option(str, description="For example Franklin and Lamar (1.6%).", default=""), # type: ignore
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              shared_gd_link: Option(str, description=SHARED_GD_LINK_DESC, default="") # type: ignore
            ) -> None:
        
        if maintitle == "" and subtitle == "":
            await ctx.respond(embed=embTitleErr)
            return
        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return
        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        C1socket = SocketPS(IP, PORT_CECIE)
        mountPaths = []

        msg = ctx

        try: 
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=embTitleChange)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
                
        batches = len(uploaded_file_paths)
        batch = SaveBatch(C1ftp, C1socket, user_id, [], mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch)

        i = 1
        for entry in uploaded_file_paths:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError as e:
                await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()

                    embTitleChange1 = discord.Embed(
                        title="Title altering process: Initializng",
                        description=f"Processing {savefile.basename} (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    embTitleChange1.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embTitleChange1)

                    await savefile.dump()
                    await savefile.download_sys_elements([savefile.ElementChoice.SFO])
                    handleTitles(savefile.sfo_ctx, maintitle, subtitle)
                    await savefile.resign()

                    embTitleSuccess = discord.Embed(
                        title="Title altering process: Successful",
                        description=f"Altered the save titles of **{savefile.basename}** (save {j}/{batch.savecount}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    embTitleSuccess.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=embTitleSuccess)
                    j += 1

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release(ctx.author.id)
                    return

            embTdone = discord.Embed(
                title="Title altering process: Successful",
                description=f"Altered the save titles of **{batch.printed}**, and resigned to **{playstation_id or user_id}** (batch {i}/{batches}).",
                colour=Color.DEFAULT.value
            )
            embTdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embTdone)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except (GDapiError, discord.HTTPException) as e:
                await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Change(bot))