import aiofiles.ospath
import discord
import asyncio
import aiofiles.os
import os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_ID_DESC, CON_FAIL, CON_FAIL_MSG,
    logger, Color, Embed_t,
    embpng, emb6, embpng1, embpng2, embTitleChange, embTitleErr,
    ICON0_FORMAT, ICON0_MAXSIZE, ICON0_NAME
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple, enumerateFiles
from utils.extras import generate_random_string, obtain_savenames, pngprocess
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, send_final
from utils.orbis import handleTitles, OrbisError
from utils.exceptions import PSNIDError, FileError

class Change(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    change_group = discord.SlashCommandGroup("change")
    
    @change_group.command(description="Changes the picture of your save, this is just cosmetic.")
    async def picture(
              self, 
              ctx: discord.ApplicationContext, 
              picture: discord.Attachment, 
              playstation_id: Option(str, description=PS_ID_DESC, default="") # type: ignore
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
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
                
        savenames = await obtain_savenames(newUPLOAD_ENCRYPTED)

        if len(uploaded_file_paths) >= 2:
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)
                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    await msg.edit(embed=embpng1)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    await msg.edit(embed=embpng2)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.swappng(location_to_scesys)
                    await C1ftp.dlparam(location_to_scesys, user_id)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    embpngs = discord.Embed(
                        title="PNG process: Successful",
                        description=f"Altered the save png of **{save}**.",
                        colour=Color.DEFAULT.value
                    )
                    embpngs.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                    await msg.edit(embed=embpngs)

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return

            if len(savenames) == 1:
                finishedFiles = "".join(savenames)
            else: finishedFiles = ", ".join(savenames)

            embPdone = discord.Embed(
                title="PNG process: Successful",
                description=f"Altered the save png of **{finishedFiles}** and resigned to '*{playstation_id or user_id}**.",
                colour=Color.DEFAULT.value
            )
            embPdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            await msg.edit(embed=embPdone)

            try: 
                await send_final(d_ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
            except GDapiError as e:
                await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return
            
            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

        else:
            await msg.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

    @change_group.command(description="Change the titles of your save.")
    async def title(
              self, 
              ctx: discord.ApplicationContext, 
              playstation_id: Option(str, description=PS_ID_DESC, default=""), # type: ignore
              maintitle: Option(str, description="For example Grand Theft Auto V.", default=""), # type: ignore
              subtitle: Option(str, description="For example Franklin and Lamar (1.6%).", default="") # type: ignore
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
            msg = await ctx.edit(embed=embTitleChange)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
                
        savenames = await obtain_savenames(newUPLOAD_ENCRYPTED)

        if len(uploaded_file_paths) >= 2:
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            uploaded_file_paths = enumerateFiles(uploaded_file_paths, random_string)
            for save in savenames:
                realSave = f"{save}_{random_string}"
                random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)

                embTitleChange1 = discord.Embed(
                    title="Change title: Processing",
                    description=f"Processing {save}.",
                    colour=Color.DEFAULT.value
                )
                embTitleChange1.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                try:
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save), os.path.join(newUPLOAD_ENCRYPTED, realSave))
                    await aiofiles.os.rename(os.path.join(newUPLOAD_ENCRYPTED, save + ".bin"), os.path.join(newUPLOAD_ENCRYPTED, realSave + ".bin"))
                    await msg.edit(embed=embTitleChange1)
                    await C1ftp.uploadencrypted_bulk(realSave)
                    mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
                    await C1ftp.make1(mount_location_new)
                    mountPaths.append(mount_location_new)
                    await C1socket.socket_dump(mount_location_new, realSave)
                    location_to_scesys = mount_location_new + "/sce_sys"
                    await C1ftp.dlparamonly_grab(location_to_scesys)
                    await handleTitles(newPARAM_PATH, user_id, maintitle, subtitle)
                    await C1ftp.upload_sfo(newPARAM_PATH, location_to_scesys)
                    await C1socket.socket_update(mount_location_new, realSave)
                    await C1ftp.dlencrypted_bulk(False, user_id, realSave)

                    embTitleSuccess = discord.Embed(
                        title="Title altering process: Successful",
                        description=f"Altered the save titles of **{save}**.",
                        colour=Color.DEFAULT.value
                    )
                    embTitleSuccess.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

                    await msg.edit(embed=embTitleSuccess)

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    status = "expected"
                    if isinstance(e, OSError) and e.errno in CON_FAIL:
                        e = CON_FAIL_MSG
                    elif isinstance(e, OSError):
                        e = BASE_ERROR_MSG
                        status = "unexpected"
                    await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - ({status})")
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    return
            
            if len(savenames) == 1:
                finishedFiles = "".join(savenames)
            else: finishedFiles = ", ".join(savenames)

            embTdone = discord.Embed(
                title="Title altering process: Successful",
                description=f"Altered the save titles of **{finishedFiles}**, and resigned to **{playstation_id or user_id}**.",
                colour=Color.DEFAULT.value
            )
            embTdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

            await msg.edit(embed=embTdone)

            try: 
                await send_final(d_ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
            except GDapiError as e:
                await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)

        else:
            await msg.edit(embed=emb6)
            cleanupSimple(workspaceFolders)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Change(bot))