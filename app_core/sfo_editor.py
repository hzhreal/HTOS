import aiofiles
from nicegui import ui, app
from webview import FileDialog
from aiofiles.ospath import isfile

from app_core.models import Logger
from app_core.helpers import int_validation
from utils.constants import SAVEBLOCKS_MIN, SAVEBLOCKS_MAX
from utils.orbis import SFOContext, checkid
from utils.exceptions import OrbisError

class SFOEditor(SFOContext):
    def __init__(self) -> None:
        super().__init__()
        self.tab = ui.tab("SFO")
        self.sfopath = ""

    def construct(self) -> None:
        with ui.row():
            ui.button("Select param.sfo file", on_click=self.on_click)
            self.sfopath_label = ui.markdown()

        with ui.row():
            self.account_id = ui.input(
                "ACCOUNT_ID (uint64 in hexadecimal)",
                placeholder="0123456789ABCDEF",
                validation={"Invalid account ID!": self.accid_0x_check}
            ).classes("w-64").props("clearable")
            self.attribute = ui.input(
                "ATTRIBUTE (uint32)",
                validation={"Input value is not a uint32!": lambda s: int_validation(s, 0, 0xFF_FF_FF_FF)}
            ).classes("w-64").props("clearable")
            self.category = ui.input(
                "CATEGORY (utf-8)"
            ).classes("w-64").props("clearable")
        with ui.row():
            self.detail = ui.input(
                "DETAIL (utf-8)"
            ).classes("w-64").props("clearable")
            self.format = ui.input(
                "FORMAT (utf-8)"
            ).classes("w-64").props("clearable")
            self.maintitle = ui.input(
                "MAINTITLE (utf-8)"
            ).classes("w-64").props("clearable")
        with ui.row():
            # parent class has attribute called param
            self.params_ = ui.input(
                "PARAMS (utf-8-special)"
            ).classes("w-64").props("clearable")
            self.savedata_blocks = ui.input(
                "SAVEDATA_BLOCKS (uint64)",
                validation={
                    f"Input value must be between {SAVEBLOCKS_MIN} and {SAVEBLOCKS_MAX}!": lambda s: int_validation(s, SAVEBLOCKS_MIN, SAVEBLOCKS_MAX)
                }
            ).classes("w-64").props("clearable")
            self.savedata_directory = ui.input(
                "SAVEDATA_DIRECTORY (utf-8)"
            ).classes("w-64").props("clearable")
        with ui.row():
            self.savedata_list_param = ui.input(
                "SAVEDATA_LIST_PARAM (uint32)",
                validation={"Input value is not a uint32!": lambda s: int_validation(s, 0, 0xFF_FF_FF_FF)}
            ).classes("w-64").props("clearable")
            self.subtitle = ui.input(
                "SUBTITLE (utf-8)"
            ).classes("w-64").props("clearable")
            self.title_id = ui.input(
                "TITLE_ID (utf-8)"
            ).classes("w-64").props("clearable")

        self.map = {
            "ACCOUNT_ID": self.account_id,
            "ATTRIBUTE": self.attribute,
            "CATEGORY": self.category,
            "DETAIL": self.detail,
            "FORMAT": self.format,
            "MAINTITLE": self.maintitle,
            "PARAMS": self.params_,
            "SAVEDATA_BLOCKS": self.savedata_blocks,
            "SAVEDATA_DIRECTORY": self.savedata_directory,
            "SAVEDATA_LIST_PARAM": self.savedata_list_param,
            "SUBTITLE": self.subtitle,
            "TITLE_ID": self.title_id,
        }

        with ui.dialog() as dialog, ui.card().classes("w-full"):
            self.info = Logger()
            ui.button("Close", on_click=dialog.close)
        self.info_btn = ui.button("Display info", on_click=dialog.open)

        self.save_btn = ui.button("Save", on_click=self.on_save)
        self.disable_buttons()

    async def on_start(self) -> None:
        if not await isfile(self.sfopath):
            ui.notify("Invalid path!")
            return
        
        try:
            async with aiofiles.open(self.sfopath, "rb") as sfo:
                self.sfo_data = bytearray(await sfo.read())
            self.read()
        except OrbisError as e:
            ui.notify(e)
            return
        except Exception:
            ui.notify("Unexpected error!")
            return
        
        self.p_data = self.param_data.copy()
        for param in self.p_data:
            self.map[param["key"]].value = param["converted_value"].rstrip("\x00")
        self.print_info()
        
        self.enable_buttons()

    async def on_save(self) -> None:
        parameters = {
            "ACCOUNT_ID": self.account_id.value,
            "ATTRIBUTE": self.attribute.value,
            "CATEGORY": self.category.value,
            "DETAIL": self.detail.value,
            "FORMAT": self.format.value,
            "MAINTITLE": self.maintitle.value,
            "PARAMS": self.params_.value,
            "SAVEDATA_BLOCKS": self.savedata_blocks.value,
            "SAVEDATA_DIRECTORY": self.savedata_directory.value,
            "SAVEDATA_LIST_PARAM": self.savedata_list_param.value,
            "SUBTITLE": self.subtitle.value,
            "TITLE_ID": self.title_id.value
        }

        try:
            # create backup
            bak_path = self.sfopath + ".bak"
            async with aiofiles.open(bak_path, "wb") as sfo:
                await sfo.write(self.sfo_data)
            ui.notify(f"Created {bak_path}.")

            for key, val in parameters.items():
                self.sfo_patch_parameter(key, val)
            await self.write()
        except OrbisError as e:
            ui.notify(e)
            return
        except ValueError:
            ui.notify("Invalid value inputted!")
            return
        except Exception:
            ui.notify("Unexpected error!")
            return

        ui.notify("Saved!")
    
    async def on_click(self) -> None:
        f = await app.native.main_window.create_file_dialog(dialog_type=FileDialog.OPEN)
        if f:
            self.disable_buttons()
            self.sfopath = f[0]
            self.sfopath_label.set_content(f"```{self.sfopath}```")
        await self.on_start()

    def disable_buttons(self) -> None:
        self.info_btn.disable()
        self.save_btn.disable()
    
    def enable_buttons(self) -> None:
        self.info_btn.enable()
        self.save_btn.enable()
    
    def read(self) -> None:
        self.sfo_read(self.sfo_data)
        self.param_data = self.sfo_get_param_data()
    
    async def write(self) -> None:
        self.sfo_data = self.sfo_write()
        async with aiofiles.open(self.sfopath, "wb") as sfo:
            await sfo.write(self.sfo_data)
    
    def print_info(self) -> None:
        s = "```\n"
        for param in self.p_data:
            for key, value in param.items():
                s += f"{key}: {value}\n"
            s += "\n"
        s += "\n```"
        self.info.write(None, s)
    
    @staticmethod
    def accid_0x_check(s: str) -> bool:
        if s.lower().startswith("0x"):
            s = s[2:]
        return checkid(s)