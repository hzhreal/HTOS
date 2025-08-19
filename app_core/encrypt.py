import asyncio
import os

from nicegui import ui, app
from webview import FileDialog
from aiofiles.ospath import isdir, getsize
from aiofiles.os import makedirs

from app_core.models import Profiles, Logger, Settings, TabBase
from app_core.helpers import prepare_save_input_folder, calculate_foldersize
from network import C1socket, FTPps, SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR
from utils.workspace import initWorkspace, cleanup, cleanupSimple
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import OrbisError, FileError
from utils.conversions import bytes_to_mb
from utils.extras import completed_print

class Encrypt(TabBase):
    def __init__(self, profiles: Profiles, settings: Settings) -> None:
        super().__init__("Encrypt", profiles, settings)
        self.encrypt_folder = ""
        self.event = asyncio.Event() # to prompt user to upload encrypt folder

    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of savefiles", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder)
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder)
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.encrypt_folder_list = Logger()
        self.logger = Logger()
        with ui.row():
            self.encrypt_button = ui.button("Select folder you want to encrypt", on_click=self.on_encrypt_folder)
            self.encrypt_label = ui.markdown()
        self.continue_button = ui.button("Continue", on_click=self.on_continue)
        self.hide_encrypt_objs()

    async def on_start(self) -> None:
        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        if not self.profiles.is_selected():
            ui.notify("No profile selected!")
            return
        self.disable_buttons()

        p = self.profiles.selected_profile.copy()

        self.logger.clear()
        self.logger.info("Starting encrypt...")

        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        for folder in workspaceFolders:
            try:
                await makedirs(folder, exist_ok=True)
            except OSError:
                self.logger.exception("Failed to create workspace. Stopped.")
                self.enable_buttons()
                return

        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    self.out_folder, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mount_paths = []

        try:
            saves = await prepare_save_input_folder(self.settings, self.logger, self.in_folder, newUPLOAD_ENCRYPTED)
        except OrbisError as e:
            await cleanupSimple(workspaceFolders)
            self.logger.error(str(e) + " Stopping...")
            self.enable_buttons()
            return
        except OSError:
            await cleanupSimple(workspaceFolders)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return

        batches = len(saves)
        batch = SaveBatch(C1ftp, C1socket, p.account_id, [], mount_paths, self.out_folder)
        savefile = SaveFile("", batch)
        
        i = 1
        for entry in saves:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError:
               await cleanup(C1ftp, workspaceFolders, None, mount_paths)
               self.logger.exception("Unexpected error. Stopping...")
               self.enable_buttons()
               return
            
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    pfs_size = await getsize(savepath) # check has already been done
                    await savefile.construct()
                    info = f"(save {j}/{batch.savecount}, batch {i}/{batches})"
                    self.logger.info(f"Encrypting **{savefile.basename}**, {info}...")

                    await savefile.dump()
                    await savefile.download_sys_elements([savefile.ElementChoice.SFO])

                    files = await C1ftp.list_files(batch.mount_location)
                    if len(files) == 0:
                        raise FileError("Could not list any decrypted saves!")
                    parsed_list = self.parse_filelist(files)
                    t = f"### {savefile.basename} ({savefile.title_id})\n\n" + parsed_list
                    self.encrypt_folder_list.write(None, t)
                    self.logger.info("Waiting for folder to encrypt...")
                    await self.event.wait()

                    encrypt_foldersize, encrypt_files = await calculate_foldersize(self.settings, self.encrypt_folder)
                    if encrypt_foldersize > pfs_size:
                        raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(pfs_size)} MB!")
                    await C1ftp.upload_folder(batch.mount_location, self.encrypt_folder)
                    idx = len(self.u) + (self.encrypt_folder[-1] != os.path.sep)
                    completed = [x[idx:] for x in encrypt_files]
                    dec_print = completed_print(completed)

                    await savefile.download_sys_elements([savefile.ElementChoice.SFO])
                    await savefile.resign()
                    self.logger.info(f"Encrypted {dec_print} into **{savefile.basename}** for {p}, {info}.")

                except (SocketError, FTPError, OrbisError, FileError, OSError) as e:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.error(str(e) + " Stopping...")
                    self.event.clear()
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.event.clear()
                    self.enable_buttons()
                    return
                j += 1
            await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
            self.logger.info(f"Encrypted files into **{batch.printed}** for {p} (batch {i}/{batches}).")
            self.logger.info(f"Batch can be found at ```{batch.fInstance.download_encrypted_path}```.")
            i += 1
        self.logger.info("Done!")
        self.event.clear()
        self.enable_buttons()

    async def on_encrypt_folder(self) -> None:
        folder = await app.native.main_window.create_file_dialog(dialog_type=FileDialog.FOLDER)
        if folder:
            self.encrypt_folder = folder[0]
            self.encrypt_folder_label.set_content(f"```{self.encrypt_folder}```")

    async def validate_encrypt_folder(self) -> bool:
        return await isdir(self.encrypt_folder)
    
    def on_continue(self) -> None:
        if not self.validate_encrypt_folder():
            ui.notify("Invalid paths!")
            return
        self.hide_encrypt_objs()
        self.event.set()

    def hide_encrypt_objs(self) -> None:
        self.encrypt_folder_list.hide()
        self.encrypt_folder_list.clear()
        self.encrypt_button.set_visibility(False)
        self.encrypt_label.set_visibility(False)
        self.continue_button.set_visibility(False)

    def show_encrypt_objs(self) -> None:
        self.encrypt_folder_list.show()
        self.encrypt_button.set_visibility(False)
        self.encrypt_label.set_visibility(True)
        self.continue_button.set_visibility(True)

    def parse_filelist(files: list[str]) -> str:
        s = "```"
        for f in files:
            s += f
        s += "```"