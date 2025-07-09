import discord
import asyncio
import shutil
import aiofiles.os
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, C1socket, FTPError, SocketError
from google_drive import gdapi, GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, ZIPOUT_NAME, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, COMMAND_COOLDOWN,
    XENO2_TITLEID, MGSV_GZ_TITLEID, MGSV_TPP_TITLEID,
    logger, Color, Embed_t,
    emb21, emb20
)
from utils.workspace import initWorkspace, makeWorkspace, cleanup, cleanupSimple
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, send_final
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError, WorkspaceError, OrbisError
from utils.instance_lock import INSTANCE_LOCK_global

class ReRegion(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @discord.slash_command(description="Change the region of a save (Must be from the same game).")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def reregion(
              self, 
              ctx: discord.ApplicationContext, 
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
        mountPaths = []

        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await gdapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=emb21)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = (await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=2, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False))[0]
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

        batch = SaveBatch(C1ftp, C1socket, user_id, uploaded_file_paths, mountPaths, newDOWNLOAD_ENCRYPTED)
        savefile = SaveFile("", batch, True)
        try:
            await batch.construct()
            savefile.path = uploaded_file_paths[0].removesuffix(".bin")
            await savefile.construct()

            embkstone1 = discord.Embed(
                title="Obtain process: Keystone",
                description=f"Obtaining keystone from file: **{savefile.basename}**, please wait...",
                colour=Color.DEFAULT.value
            )
            embkstone1.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embkstone1)

            await savefile.dump()
            await savefile.download_sys_elements([savefile.ElementChoice.SFO, savefile.ElementChoice.KEYSTONE])

            target_titleid = savefile.title_id
            
            embkstone2 = discord.Embed(
                title="Obtain process: Keystone",
                description=f"Keystone from **{target_titleid}** obtained.",
                colour=Color.DEFAULT.value
            )
            embkstone2.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embkstone2)

            shutil.rmtree(newUPLOAD_ENCRYPTED)
            await aiofiles.os.mkdir(newUPLOAD_ENCRYPTED)

            await C1ftp.deleteList(PS_UPLOADDIR, [savefile.realSave, savefile.realSave + ".bin"])

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

        try:
            await msg.edit(embed=emb20)
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = gdapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except (TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
   
        if ((target_titleid in XENO2_TITLEID) or (target_titleid in MGSV_TPP_TITLEID) or (target_titleid in MGSV_GZ_TITLEID)):
            special_reregion = True
        else:
            special_reregion = False

        batches = len(uploaded_file_paths)

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

            extra_msg = ""
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()
                    savefile.title_id = target_titleid
                    savefile.downloaded_sys_elements.add(savefile.ElementChoice.KEYSTONE)

                    emb4 = discord.Embed(
                        title="Re-regioning process: Encrypted",
                        description=f"Your save (**{savefile.basename}**) is being re-regioned & resigned, (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    emb4.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb4)

                    await savefile.dump()
                    await savefile.resign()

                    emb5 = discord.Embed(
                        title="Re-regioning (Encrypted): Successful",
                        description=f"**{savefile.basename}** re-regioned & resigned to **{playstation_id or user_id}** (**{target_titleid}**), (save {j}/{batch.savecount}, batch {i}/{batches}).",
                        colour=Color.DEFAULT.value
                    )
                    emb5.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb5)
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

            embRgdone = discord.Embed(
                title="Re-region: Successful",
                description=f"**{batch.printed}** re-regioned & resigned to **{playstation_id or user_id}** (**{target_titleid}**), (batch {i}/{batches}).",
                colour=Color.DEFAULT.value
            )
            embRgdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            try:
                await msg.edit(embed=embRgdone)
            except discord.HTTPException as e:
                logger.exception(f"Error while editing msg: {e}")

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            if special_reregion and not extra_msg and j > 2:
                extra_msg = "Make sure to remove the random string after and including '_' when you are going to copy that file to the console. Only required if you re-regioned more than 1 save at once."

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid, extra_msg)
            except (GDapiError, discord.HTTPException) as e:
                await errorHandling(msg, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release(ctx.author.id)
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(ReRegion(bot))