import os

from nicegui import ui
from aiofiles.os import makedirs, mkdir, rename

from app_core.models import Logger, Settings, TabBase
from app_core.helpers import prepare_save_input_folder
from data.crypto.helpers import extra_decrypt
from data.crypto.common import CryptoError
from network import C1socket, FTPps, SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR
from utils.workspace import initWorkspace, cleanup, cleanupSimple
from utils.orbis import SaveBatch, SaveFile
from utils.namespaces import Crypto
from utils.exceptions import OrbisError

class Decrypt(TabBase):
    def __init__(self, settings: Settings) -> None:
        super().__init__("Decrypt", None, settings)
    
    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of savefiles", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder).props("clearable")
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder).props("clearable")
        self.include_sce_sys_checkbox = ui.checkbox("Include the sce_sys folder", value=True)
        self.ignore_secondlayer_checks_checkbox = ui.checkbox("Ignore secondlayer checks")
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.logger = Logger()

    async def on_start(self) -> None:
        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        self.disable_buttons()

        include_sce_sys = self.include_sce_sys_checkbox.value
        ignore_secondlayer_checks = self.ignore_secondlayer_checks_checkbox.value

        self.logger.clear()
        self.logger.info("Starting decrypt...")

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
                    newDOWNLOAD_ENCRYPTED, newPARAM_PATH, newKEYSTONE_PATH, newPNG_PATH)
        mount_paths = []

        try:
            saves = await prepare_save_input_folder(self.settings, self.logger, self.in_folder, newUPLOAD_ENCRYPTED)
        except OrbisError as e:
            await cleanupSimple(workspaceFolders)
            self.logger.error(f"`{str(e)}` Stopping...")
            self.enable_buttons()
            return
        except OSError:
            await cleanupSimple(workspaceFolders)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return

        batches = len(saves)
        batch = SaveBatch(C1ftp, C1socket, "", [], mount_paths, "")
        savefile = SaveFile("", batch)
        
        i = 1
        for entry in saves:
            batch.entry = entry
            try:
                await batch.construct()
                destination_directory_outer = os.path.join(self.out_folder, batch.rand_str) 
                await mkdir(destination_directory_outer)
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
                    destination_directory = os.path.join(destination_directory_outer, f"dec_{savefile.basename}")
                    await mkdir(destination_directory)

                    info = f"(save {j}/{batch.savecount}, batch {i}/{batches})"
                    self.logger.info(f"Decrypting **{savefile.basename}**, {info}...")

                    await savefile.dump()
                    await C1ftp.download_folder(batch.mount_location, destination_directory, not include_sce_sys)
                    await savefile.download_sys_elements([savefile.ElementChoice.SFO])

                    await rename(destination_directory, destination_directory + f"_{savefile.title_id}")
                    destination_directory += f"_{savefile.title_id}"

                    if not ignore_secondlayer_checks:
                        await extra_decrypt(None, Crypto, savefile.title_id, destination_directory, savefile.basename)

                    self.logger.info(f"Decrypted **{savefile.basename}** {info}.")
                except (SocketError, FTPError, OrbisError, CryptoError, OSError) as e:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.error(f"`{str(e)}` Stopping...")
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.enable_buttons()
                    return
                j += 1
            await cleanup(C1ftp, workspaceFolders, batch.entry, mount_paths)
            self.logger.info(f"**{batch.printed}** has been decrypted (batch {i}/{batches}).")
            self.logger.info(f"Batch can be found at ```{destination_directory_outer}```.")
            i += 1
        self.logger.info("Done!")
        self.enable_buttons()

    def disable_buttons(self) -> None:
        super().disable_buttons()
        self.include_sce_sys_checkbox.disable()
        self.ignore_secondlayer_checks_checkbox.disable()
    
    def enable_buttons(self) -> None:
        super().enable_buttons()
        self.include_sce_sys_checkbox.enable()
        self.ignore_secondlayer_checks_checkbox.enable()