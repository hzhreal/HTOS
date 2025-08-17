from nicegui import ui, app
from webview import FOLDER_DIALOG
from aiofiles.ospath import isdir
from aiofiles.os import makedirs

from app_core.models import Profiles, Logger, Settings
from app_core.helpers import prepare_save_input_folder
from network import C1socket, FTPps, SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR
from utils.workspace import initWorkspace, cleanup, cleanupSimple
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import OrbisError

class Resign:
    def __init__(self, profiles: Profiles, settings: Settings) -> None:
        self.profiles = profiles
        self.settings = settings
        self.tab = ui.tab("Resign")
        self.in_folder = ""
        self.out_folder = ""
    
    def construct(self) -> None:
        with ui.row():
            ui.button("Select folder of savefiles", on_click=self.on_input)
            self.in_label = ui.markdown()
        with ui.row():
            ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.markdown()
        ui.button("Start", on_click=self.on_start)
        self.logger = Logger()
    
    async def on_input(self) -> None:
        folder = await app.native.main_window.create_file_dialog(dialog_type=FOLDER_DIALOG)
        if folder:
            self.in_folder = folder[0]
            self.in_label.set_content(f"```{self.in_folder}```")
    
    async def on_output(self) -> None:
        folder = await app.native.main_window.create_file_dialog(dialog_type=FOLDER_DIALOG)
        if folder:
            self.out_folder = folder[0]
            self.out_label.set_content(f"```{self.out_folder}```")

    async def validation(self) -> bool:
        return await isdir(self.in_folder) and await isdir(self.out_folder)

    async def on_start(self) -> None:
        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        if not self.profiles.is_selected():
            ui.notify("No profile selected!")
            return

        p = self.profiles.selected_profile.copy()

        self.logger.clear()
        self.logger.info("Starting resign...")

        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = initWorkspace()
        workspaceFolders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        for folder in workspaceFolders:
            try:
                await makedirs(folder, exist_ok=True)
            except OSError:
                self.logger.exception("Failed to create workspace. Stopped.")
                return

        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, newDOWNLOAD_DECRYPTED, newUPLOAD_DECRYPTED, newUPLOAD_ENCRYPTED,
                    self.out_folder, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mount_paths = []

        try:
            saves = await prepare_save_input_folder(self.settings, self.logger, self.in_folder, newUPLOAD_ENCRYPTED)
        except OrbisError as e:
            cleanupSimple(workspaceFolders)
            self.logger.error(str(e) + " Stopping...")
            return
        except OSError:
            cleanupSimple(workspaceFolders)
            self.logger.exception("Unexpected error. Stopping...")
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
               return
            
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()
                    info = f"(save {j}/{batch.savecount}, batch {i}/{batches})"
                    self.logger.info(f"Resigning **{savefile.basename}**, {info}...")

                    await savefile.dump()
                    await savefile.resign()
                    self.logger.info(f"Resigned **{savefile.basename}** to {p}, {info}.")

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.error(str(e) + " Stopping...")
                    return
                except Exception:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.exception("Unexpected error. Stopping...")
                    return
                j += 1
            await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
            self.logger.info(f"**{batch.printed}** resigned to {p} (batch {i}/{batches}).")
            i += 1
        self.logger.info("Done!")