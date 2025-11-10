import os
import shutil

from nicegui import ui
from aiofiles.os import makedirs

from app_core.models import Logger, Settings, TabBase
from app_core.helpers import prepare_files_input_folder
from data.cheats.quickcodes import QuickCodes as QC
from data.cheats.quickcodes import QuickCodesError
from utils.workspace import init_workspace, cleanup_simple
from utils.extras import completed_print

class QuickCodes(TabBase):
    def __init__(self, settings: Settings) -> None:
        super().__init__("Quickcodes", None, settings)

    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of savegames", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder).props("clearable")
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder).props("clearable")
        self.codes_obj = ui.textarea(
            "Enter quick codes", 
            placeholder="80010008 EA372703\n00140000 00000000\n180000E8 0000270F"
        ).props("rows=15 outlined clearable").classes("w-1/2")
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.logger = Logger(self.settings)

    async def on_start(self) -> None:
        if not self.codes_obj.value:
            ui.notify("No codes inputted!")
            return
        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        try:
            qc = QC("", self.codes_obj.value)
        except QuickCodesError as e:
            ui.notify(e)
            return
        self.disable_buttons()

        self.logger.clear()
        self.logger.info("Applying codes...")

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
            
        try:
            files = await prepare_files_input_folder(self.settings, self.in_folder, newUPLOAD_DECRYPTED)
        except OSError:
            await cleanup_simple(workspace_folders)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return
        
        batches = len(files)
        
        i = 1
        for entry in files:
            count_entry = len(entry)
            completed = []
            dname = os.path.dirname(entry[0])
            out_path = dname
            rand_str = os.path.basename(dname)

            j = 1
            for savegame in entry:
                info = f"(file {j}/{count_entry}, batch {i}/{batches})"
                basename = os.path.basename(savegame)
                self.logger.info(f"Applying codes to {basename}, {info}.")

                qc.filePath = savegame
                try:
                    await qc.apply_code()
                except QuickCodesError as e:
                    await cleanup_simple(workspace_folders)
                    self.logger.error(f"`{str(e)}` Stopping...")
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanup_simple(workspace_folders)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.enable_buttons()
                    return
                
                completed.append(basename)
                j += 1
            
            out = os.path.join(self.out_folder, rand_str)
            finished_files = completed_print(completed)
            shutil.copytree(out_path, out, dirs_exist_ok=True)

            self.logger.info(f"Applied codes to **{finished_files}** (batch {i}/{batches}).")
            self.logger.info(f"Batch can be found at ```{out}```.")
            i += 1
        await cleanup_simple(workspace_folders)
        self.logger.info("Done!")
        self.enable_buttons()

    def disable_buttons(self) -> None:
        super().disable_buttons()
        self.codes_obj.disable()
    
    def enable_buttons(self) -> None:
        super().enable_buttons()
        self.codes_obj.enable()
