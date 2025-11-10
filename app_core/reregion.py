import shutil

from nicegui import ui, app
from nicegui.events import ValueChangeEventArguments
from webview import FileDialog
from aiofiles.os import makedirs, mkdir

from app_core.models import Profiles, Settings, Logger, TabBase
from app_core.helpers import prepare_save_input_folder, check_save, prepare_single_save_folder
from network import C1socket, FTPps, SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR, XENO2_TITLEID, MGSV_GZ_TITLEID, MGSV_TPP_TITLEID
from utils.workspace import init_workspace, cleanup, cleanup_simple
from utils.orbis import SaveBatch, SaveFile
from utils.exceptions import OrbisError

class Reregion(TabBase):
    def __init__(self, profiles: Profiles, settings: Settings) -> None:
        super().__init__("Re-region", profiles, settings)
        self.in_sample_file = ""

    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of savefiles", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder).props("clearable")
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder).props("clearable")
        with ui.row():
            self.sample_save_button = ui.button("Select sample save from your region (target title id)", on_click=self.on_sample_save)
            self.sample_save_label = ui.input(on_change=self.on_sample_save_in).props("clearable")
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.logger = Logger(self.settings)

    async def on_start(self) -> None:
        if not await self.validation():
            ui.notify("Invalid paths/files!")
            return
        if not self.profiles.is_selected():
            ui.notify("No profile selected!")
            return
        self.disable_buttons()

        p = self.profiles.selected_profile.copy()

        self.logger.clear()
        self.logger.info("Starting re-region...")

        newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH = init_workspace()
        workspace_folders = [newUPLOAD_ENCRYPTED, newUPLOAD_DECRYPTED, newDOWNLOAD_ENCRYPTED, 
                            newPNG_PATH, newPARAM_PATH, newDOWNLOAD_DECRYPTED, newKEYSTONE_PATH]
        for folder in workspace_folders:
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
            real_sample_savepair = await prepare_single_save_folder(self.sample_savepair, newUPLOAD_ENCRYPTED)
        except OSError:
            await cleanup_simple(workspace_folders)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return

        batch = SaveBatch(C1ftp, C1socket, p.account_id, list(real_sample_savepair), mount_paths, self.out_folder)
        savefile = SaveFile("", batch, True)
        try:
            await batch.construct()
            savefile.path = real_sample_savepair[0]
            await savefile.construct()
            self.logger.info(f"Obtaining keystone from {savefile.basename}...")

            await savefile.dump()
            await savefile.download_sys_elements([savefile.ElementChoice.SFO, savefile.ElementChoice.KEYSTONE])
            target_titleid = savefile.title_id
            self.logger.info(f"Keystone from {savefile.basename} ({target_titleid}) obtained.")

            shutil.rmtree(newUPLOAD_ENCRYPTED)
            await mkdir(newUPLOAD_ENCRYPTED)
            await C1ftp.delete_list(PS_UPLOADDIR, [savefile.realSave, savefile.realSave + ".bin"])
        except (SocketError, FTPError, OrbisError, OSError) as e:
            await cleanup(C1ftp, workspace_folders, batch.entry, mount_paths)
            self.logger.error(f"`{str(e)}` Stopping...")
            self.enable_buttons()
            return
        
        try:
            saves = await prepare_save_input_folder(self.settings, self.logger, self.in_folder, newUPLOAD_ENCRYPTED)
        except OrbisError as e:
            await cleanup(C1ftp, workspace_folders, None, mount_paths)
            self.logger.error(f"`{str(e)}` Stopping...")
            self.enable_buttons()
            return
        except OSError:
            await cleanup(C1ftp, workspace_folders, None, mount_paths)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return
        
        if ((target_titleid in XENO2_TITLEID) or (target_titleid in MGSV_TPP_TITLEID) or (target_titleid in MGSV_GZ_TITLEID)):
            special_reregion = True
        else:
            special_reregion = False
        
        batches = len(saves)
        
        i = 1
        for entry in saves:
            batch.entry = entry
            try:
                await batch.construct()
            except OSError:
               await cleanup(C1ftp, workspace_folders, None, mount_paths)
               self.logger.exception("Unexpected error. Stopping...")
               self.enable_buttons()
               return
            
            extra_msg = ""
            j = 1
            for savepath in batch.savenames:
                savefile.path = savepath
                try:
                    await savefile.construct()
                    savefile.title_id = target_titleid
                    savefile.downloaded_sys_elements.add(savefile.ElementChoice.KEYSTONE)

                    info = f"(save {j}/{batch.savecount}, batch {i}/{batches})"
                    self.logger.info(f"Re-regioning **{savefile.basename}**, {info}...")

                    await savefile.dump()
                    await savefile.resign()
                    self.logger.info(f"Re-regioned **{savefile.basename}** to {p} (**{target_titleid}**), {info}.")

                except (SocketError, FTPError, OrbisError, OSError) as e:
                    await cleanup(C1ftp, workspace_folders, batch.entry, mount_paths)
                    self.logger.error(f"`{str(e)}` Stopping...")
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanup(C1ftp, workspace_folders, batch.entry, mount_paths)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.enable_buttons()
                    return
                j += 1
            await cleanup(C1ftp, workspace_folders, batch.entry, mount_paths)
            self.logger.info(f"**{batch.printed}** re-regioned to {p} (batch {i}/{batches}).")
            self.logger.info(f"Batch can be found at ```{batch.fInstance.download_encrypted_path}```.")
            if special_reregion and not extra_msg and j > 2:
                extra_msg = "Make sure to remove the random string after and including '_' when you are going to copy that file to the console. Only required if you re-regioned more than 1 save at once."
            self.logger.info(extra_msg)
            i += 1
        self.logger.info("Done!")
        self.enable_buttons()

    async def on_sample_save(self) -> None:
        f = await app.native.main_window.create_file_dialog(FileDialog.OPEN)
        if f:
            self.in_sample_file = f[0]
            self.sample_save_label.set_value(self.in_sample_file)
        
    def on_sample_save_in(self, event: ValueChangeEventArguments) -> None:
        self.in_sample_file = event.value

    async def validation(self) -> bool:
        t_v = await super().validation()
        if not t_v:
            return False
        t_v, savepair = await check_save(self.in_sample_file)
        if not t_v:
            return False
        self.sample_savepair = savepair
        return True

    def disable_buttons(self) -> None:
        super().disable_buttons()
        self.sample_save_button.disable()
        self.sample_save_label.disable()
    
    def enable_buttons(self) -> None:
        super().enable_buttons()
        self.sample_save_button.enable()
        self.sample_save_label.disable()
