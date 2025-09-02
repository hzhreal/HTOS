import os
import shutil
import asyncio
from functools import partial
from typing import Callable, Awaitable

from nicegui import ui
from aiofiles.os import makedirs

from app_core.models import Logger, Settings, TabBase
from app_core.helpers import prepare_files_input_folder
from data.converter import ConverterError
from data.crypto.common import CryptoError
from utils.namespaces import Converter, Crypto
from utils.workspace import initWorkspace, cleanupSimple
from utils.extras import completed_print

class Convert(TabBase):
    def __init__(self, settings: Settings) -> None:
        super().__init__("Convert", None, settings)
        self.event = asyncio.Event()
        self.special_case_result: str | ConverterError = ""

    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of savegames", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder).props("clearable")
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder).props("clearable")
        self.game_dropdown = ui.select(["GTA V", "RDR 2", "BL 3", "TTWL"])
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.logger = Logger(self.settings)

    async def on_start(self) -> None:
        if not self.game_dropdown.value:
            ui.notify("Game not selected!")
            return
        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        self.disable_buttons()

        self.logger.clear()
        self.logger.info("Starting conversion...")

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
            
        try:
            files = await prepare_files_input_folder(self.settings, self.in_folder, newUPLOAD_DECRYPTED)
        except OSError:
            await cleanupSimple(workspaceFolders)
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
                self.logger.info(f"Converting {basename}, {info}.")

                try:
                    match self.game_dropdown.value:
                        case "GTA V":
                            result = await Converter.Rstar.convertFile_GTAV(savegame)
                    
                        case "RDR 2":
                            result = await Converter.Rstar.convertFile_RDR2(savegame)

                        case "BL 3":
                            result = await Converter.BL3.convertFile(None, None, savegame, False, None)
                            if not result:
                                result = await self.special_case_wrapper(savegame)
                        
                        case "TTWL":
                            result = await Converter.BL3.convertFile(None, None, savegame, True, None)
                            if not result:
                                result = await self.special_case_wrapper(savegame)
                
                except ConverterError as e:
                    await cleanupSimple(workspaceFolders)
                    self.logger.error(f"`{str(e)}` Stopping...")
                    self.event.clear()
                    self.enable_buttons()
                    return
                except Exception:
                    await cleanupSimple(workspaceFolders)
                    self.logger.exception("Unexpected error. Stopping...")
                    self.event.clear()
                    self.enable_buttons()
                    return
                
                if result == "ERROR":
                    await cleanupSimple(workspaceFolders)
                    self.logger.error("Invalid save. Stopping...")
                    self.event.clear()
                    self.enable_buttons()
                    return
                completed.append(basename)
                self.event.clear()
                self.logger.info(f"Converted {basename} (```{result}```), ({info}).")
                j += 1
            
            out = os.path.join(self.out_folder, rand_str)
            finished_files = completed_print(completed)
            shutil.copytree(out_path, out, dirs_exist_ok=True)

            self.logger.info(f"Converted **{finished_files}** (batch {i}/{batches}).")
            self.logger.info(f"Batch can be found at ```{out}```.")
            i += 1
        await cleanupSimple(workspaceFolders)
        self.logger.info("Done!")
        self.enable_buttons()

    async def special_case_handler(self, savegame: str) -> None:
        if self.game_dropdown.value in ("BL 3", "TTWL"):
            ttwl = savegame == "TTWL"
            with ui.dialog() as dialog, ui.card():
                self.dialog = dialog
                with ui.dropdown_button(f"Select operation ({os.path.basename(savegame)})", auto_close=True):
                    ui.item("PS4 -> PC", on_click=partial(self.special_case_assign, partial(self.bl3_ps4_to_pc_callback, savegame, ttwl)))
                    ui.item("PC -> PS4", on_click=partial(self.special_case_assign, partial(self.bl3_pc_to_ps4_callback, savegame, ttwl)))
            self.dialog.on("hide", dialog.open)
            self.dialog.open()
            await self.event.wait()
    
    async def special_case_assign(self, call: partial[Callable[[], Awaitable[str]]]) -> None:
        try:
            res = await call()
            self.special_case_result = res
        except ConverterError as e:
            self.special_case_result = e
        finally:
            self.dialog.close()
            self.dialog.delete()
            self.event.set()

    async def special_case_wrapper(self, savegame: str) -> str:
        await self.special_case_handler(savegame)
        if isinstance(self.special_case_result, ConverterError):
            raise self.special_case_result
        return self.special_case_result
    
    @staticmethod
    async def bl3_ps4_to_pc_callback(filepath: str, ttwl: bool) -> str:
        platform = "ps4"
        try:
            await Crypto.BL3.encryptFile(filepath, "pc", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("Invalid save!")
        return Converter.BL3.obtain_ret_val(platform)
    
    @staticmethod
    async def bl3_pc_to_ps4_callback(filepath: str, ttwl: bool) -> str:
        platform = "pc"
        try:
            await Crypto.BL3.encryptFile(filepath, "ps4", ttwl)
        except CryptoError as e:
            raise ConverterError(e)
        except (ValueError, IOError, IndexError):
            raise ConverterError("Invalid save!")
        return Converter.BL3.obtain_ret_val(platform)

    def disable_buttons(self) -> None:
        super().disable_buttons()
        self.game_dropdown.disable()
    
    def enable_buttons(self) -> None:
        super().enable_buttons()
        self.game_dropdown.enable()