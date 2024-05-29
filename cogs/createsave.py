import discord
import aiofiles.os
import asyncio
import os
import shutil
from discord.ext import commands
from discord import Option
from aiogoogle import HTTPError
from network import FTPps, SocketPS, SocketError, FTPError
from google_drive import GDapi, GDapiError
from data.crypto.helpers import extra_import
from utils.constants import (
    IP, PORT_FTP, PORT_CECIE, PS_UPLOADDIR, MOUNT_LOCATION,
    SAVEBLOCKS_MAX, SCE_SYS_CONTENTS, BASE_ERROR_MSG, PS_ID_DESC, RANDOMSTRING_LENGTH, MAX_FILES, PARAM_NAME, CON_FAIL,
    Color, logger
)
from utils.workspace import makeWorkspace, WorkspaceError, initWorkspace, cleanup, cleanupSimple
from utils.helpers import errorHandling, upload2, send_final, psusername, upload2_special
from utils.orbis import resign, obtainCUSA, validate_savedirname, OrbisError
from utils.extras import generate_random_string
from utils.exceptions import PSNIDError, FileError
from utils.namespaces import Crypto

class CreateSave(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Create savedata from scratch.")
    async def createsave(
              self, 
              ctx: discord.ApplicationContext, 
              savename: Option(str, description="The name of the save."), # type: ignore
              saveblocks: Option(int, description=f"Max is {SAVEBLOCKS_MAX}, the value you put in will deterine savesize (blocks * {SAVEBLOCKS_MAX})."), # type: ignore
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
        DISC_UPL_SPLITVALUE = "SLASH"
        scesys_local = os.path.join(newUPLOAD_DECRYPTED, "sce_sys")
        os.makedirs(scesys_local)
        
        embSceSys = discord.Embed(title=f"Upload: sce_sys contents\n{savename}",
                                  description="Please attach the sce_sys files you want to upload.",
                                  colour=Color.DEFAULT.value)
        embSceSys.set_footer(text="Made by hzh.")

        embgs = discord.Embed(title=f"Upload: Gamesaves\n{savename}",
                                  description=(
                                    "Please attach the gamesaves files you want to upload.\n"
                                    "**FOLLOW THESE INSTRUCTIONS CAREFULLY**\n\n"
                                    f"For **discord uploads** rename the files according to the path they are going to have inside the savefile using the value '{DISC_UPL_SPLITVALUE}'. For example the file 'savedata' inside the data directory would be called 'data{DISC_UPL_SPLITVALUE}savedata'.\n\n"
                                    "For **google drive uploads** just create the directories on the drive and send the folder link from root, it will be recursively downloaded."
                                  ),
                                  colour=Color.DEFAULT.value)
        embgs.set_footer(text="Made by hzh.")

        try:
            user_id = await psusername(ctx, playstation_id)
            await asyncio.sleep(0.5)

            if not validate_savedirname(savename):
                raise OrbisError("Invalid savename!")
            elif saveblocks > SAVEBLOCKS_MAX:
                raise OrbisError(f"Saveblocks limit of {SAVEBLOCKS_MAX} exceeded!")
            
            savesize = saveblocks * SAVEBLOCKS_MAX

            # handle sce_sys first
            await ctx.edit(embed=embSceSys)
            uploaded_file_paths_sys = await upload2(ctx, scesys_local, max_files=len(SCE_SYS_CONTENTS), sys_files=True, ps_save_pair_upload=False, ignore_filename_check=False)
            if len(uploaded_file_paths_sys) != len(SCE_SYS_CONTENTS):
                # we are trying to have a valid save
                raise FileError("All sce_sys files are not uploaded! We are trying to create a valid save here.")

            # next, other files (gamesaves)
            await ctx.edit(embed=embgs)
            uploaded_file_paths = await upload2_special(ctx, newUPLOAD_DECRYPTED, MAX_FILES, DISC_UPL_SPLITVALUE, savesize)
        except HTTPError as e:
            err = GDapi.getErrStr_HTTPERROR(e)
            await errorHandling(ctx, err, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except (PSNIDError, TimeoutError, GDapiError, FileError, OrbisError) as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        # we dont care enough to add check if any gamesaves were uploaded
        try:
            local_scesys_files = [os.path.join(scesys_local, filename) for filename in await aiofiles.os.listdir(scesys_local)]
            sfo_path = os.path.join(scesys_local, PARAM_NAME)

            await resign(sfo_path, user_id)
            title_id = await obtainCUSA(scesys_local)
            
            for gamesave in uploaded_file_paths:
                embsl = discord.Embed(title=f"Gamesaves: Second layer\n{gamesave}",
                                  description="Checking for supported second layer encryption/compression...",
                                  colour=Color.DEFAULT.value)
                embsl.set_footer(text="Made by hzh.")
                await ctx.edit(embed=embsl)
                await asyncio.sleep(0.5)
                await extra_import(Crypto, title_id, gamesave)

            # gen a new name for file to not get overwritten with anything on the console
            random_string = generate_random_string(RANDOMSTRING_LENGTH)
            random_string_mount = generate_random_string(RANDOMSTRING_LENGTH)

            temp_savename = savename + f"_{random_string}"
            mount_location_new = MOUNT_LOCATION + "/" + random_string_mount
            location_to_scesys = mount_location_new + "/" + "sce_sys"

            await C1socket.socket_createsave(PS_UPLOADDIR, savename, saveblocks)
            
            # now mount save and get ready to upload files to it
            await C1ftp.make1(mount_location_new)
            mountPaths.append(mount_location_new)
            await C1socket.socket_dump(mount_location_new, temp_savename)

            # yh uploaded now! make sure all sce_sys files are uploaded with var
            await C1ftp.upload_scesysContents(ctx, local_scesys_files, location_to_scesys)
            shutil.rmtree(scesys_local)
            await C1ftp.ftp_upload_folder(mount_location_new, newUPLOAD_DECRYPTED)

            await C1socket.socket_update(mount_location_new, temp_savename)
            
            # make paths for save
            save_dirs = os.path.join(newDOWNLOAD_ENCRYPTED, "PS4", "SAVEDATA", user_id, title_id)
            os.makedirs(save_dirs)

            # download save at real filename path
            ftp_ctx = await C1ftp.create_ctx()
            await C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename, os.path.join(save_dirs, savename))
            await C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename + "bin", os.path.join(save_dirs, savename + ".bin"))
            await ftp_ctx.quit()
            ftp_ctx.close()
        except (SocketError, FTPError, OSError, OrbisError) as e:
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = "PS4 not connected!"
            await errorHandling(ctx, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return
        
        embRdone = discord.Embed(title="Creation process: Successful",
                            description=f"**{savename}** created & resigned to **{playstation_id or user_id}**.",
                            colour=Color.DEFAULT.value)
        embRdone.set_footer(text="Made by hzh.")
        
        await ctx.edit(embed=embRdone)

        try: 
            await send_final(ctx, "PS4.zip", newDOWNLOAD_ENCRYPTED)
        except GDapiError as e:
            await errorHandling(ctx, e, workspaceFolders, uploaded_file_paths, mountPaths, C1ftp)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return

        await asyncio.sleep(1)
        await cleanup(C1ftp, workspaceFolders, uploaded_file_paths, mountPaths)   

def setup(bot: commands.Bot) -> None:
    bot.add_cog(CreateSave(bot))