import discord
import asyncio
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, FTPError, SocketError
from google_drive import GDapi, GDapiError
from utils.constants import (
    IP, PORT_FTP, PS_UPLOADDIR, PORT_CECIE, MAX_FILES, BASE_ERROR_MSG, PS_ID_DESC, SHARED_GD_LINK_DESC, CON_FAIL, CON_FAIL_MSG, ZIPOUT_NAME,
    logger, Color, Embed_t,
    embEncrypted1
)
from utils.workspace import initWorkspace, makeWorkspace, WorkspaceError, cleanup, cleanupSimple
from utils.helpers import DiscordContext, psusername, upload2, errorHandling, send_final
from utils.orbis import OrbisError, SaveBatch, SaveFile
from utils.exceptions import PSNIDError, FileError
from utils.instance_lock import INSTANCE_LOCK_global

class Resign(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @discord.slash_command(description="Resign encrypted savefiles (the usable ones you put in the console).")
    async def resign(
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
        C1socket = SocketPS(IP, PORT_CECIE)
        mountPaths = []
        
        msg = ctx

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)
            shared_gd_folderid = await GDapi.parse_sharedfolder_link(shared_gd_link)
            msg = await ctx.edit(embed=embEncrypted1)
            msg = await ctx.fetch_message(msg.id) # use message id instead of interaction token, this is so our command can last more than 15 min
            d_ctx = DiscordContext(ctx, msg) # this is for passing into functions that need both
            uploaded_file_paths = await upload2(d_ctx, newUPLOAD_ENCRYPTED, max_files=MAX_FILES, sys_files=False, ps_save_pair_upload=True, ignore_filename_check=False)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(msg, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(msg, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release()
            return
        except Exception as e:
            await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release()
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
                await INSTANCE_LOCK_global.release()
                return
            
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()

                    emb4 = discord.Embed(
                        title="Resigning process: Encrypted",
                        description=f"Your save (**{savefile.basename}**) is being resigned, (save {j}/{batch.savecount}, batch {i}/{batches}), please wait...",
                        colour=Color.DEFAULT.value
                    )
                    emb4.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
                    await msg.edit(embed=emb4)
                    
                    await savefile.dump()
                    await savefile.resign()

                    emb5 = discord.Embed(
                        title="Resigning process (Encrypted): Successful",
                        description=f"**{savefile.basename}** resigned to **{playstation_id or user_id}** (save {j}/{batch.savecount}, batch {i}/{batches}).",
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
                    await INSTANCE_LOCK_global.release()
                    return
                except Exception as e:
                    await errorHandling(msg, BASE_ERROR_MSG, workspaceFolders, batch.entry, mountPaths, C1ftp)
                    logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
                    await INSTANCE_LOCK_global.release()
                    return
            
            embRdone = discord.Embed(
                title="Resigning process (Encrypted): Successful",
                description=f"**{batch.printed}** resigned to **{playstation_id or user_id}** (batch {i}/{batches}).",
                colour=Color.DEFAULT.value)
            embRdone.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await msg.edit(embed=embRdone)

            zipname = ZIPOUT_NAME[0] + f"_{batch.rand_str}" + f"_{i}" + ZIPOUT_NAME[1]

            try: 
                await send_final(d_ctx, zipname, C1ftp.download_encrypted_path, shared_gd_folderid)
            except GDapiError as e:
                await errorHandling(msg, e, workspaceFolders, batch.entry, mountPaths, C1ftp)
                logger.exception(f"{e} - {ctx.user.name} - (expected)")
                await INSTANCE_LOCK_global.release()
                return

            await asyncio.sleep(1)
            await cleanup(C1ftp, None, batch.entry, mountPaths)
            i += 1
        await cleanupSimple(workspaceFolders)
        await INSTANCE_LOCK_global.release()
    
def setup(bot: commands.Bot) -> None:
    bot.add_cog(Resign(bot))