from nicegui import ui
from aiofiles.os import makedirs

from app_core.models import Profiles, Settings, TabBase
from app_core.helpers import prepare_save_input_folder
from network import C1socket, FTPps, SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR
from utils.workspace import initWorkspace, cleanup, cleanupSimple
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import OrbisError

class Resign(TabBase):
    def __init__(self, profiles: Profiles, settings: Settings) -> None:
        super().__init__("Resign", profiles, settings)

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
        self.logger.info("Starting resign...")

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
                    await savefile.construct()
                    info = f"(save {j}/{batch.savecount}, batch {i}/{batches})"
                    self.logger.info(f"Resigning **{savefile.basename}**, {info}...")

                    await savefile.dump()
                    await savefile.resign()
                    self.logger.info(f"Resigned **{savefile.basename}** to {p}, {info}.")

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.error(str(e) + " Stopping...")
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.enable_buttons()
                    return
                j += 1
            await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
            self.logger.info(f"**{batch.printed}** resigned to {p} (batch {i}/{batches}).")
            self.info(f"Batch can be found at {batch.new_download_encrypted_path}.")
            i += 1
        self.logger.info("Done!")
        self.enable_buttons()