from __future__ import annotations

import os
import json
import traceback
from typing import Any, Callable
from enum import Enum, auto

from nicegui import ui, app
from webview import FOLDER_DIALOG
from aiofiles.ospath import isdir

from utils.orbis import checkid
from app_core.exceptions import ProfileError, SettingsError

class Profile:
    MAX_NAME_LENGTH = 20

    def __init__(self, name: str = "", account_id: str = "") -> None:
        self.name = name
        self.account_id = account_id
        if self.account_id:
            assert checkid(account_id)
        self.display = f"{self.name} ({self.account_id})"

    def update_display(self) -> None:
        self.display = f"{self.name} ({self.account_id})"

    def clear(self) -> None:
        self.name = ""
        self.account_id = ""
        self.update_display()

    def pad_name(self) -> str:
        return self.name.ljust(self.MAX_NAME_LENGTH)
    
    def copy(self) -> Profile:
        return Profile(self.name, self.account_id)
    
    def is_set(self) -> bool:
        t_v = bool(self.name) and bool(self.account_id)
        if t_v:
            self.update_display()
        return t_v

    def __str__(self) -> str:
        return self.display

class Profiles:
    def __init__(self, profiles_path: str) -> None:
        self.profiles_path = profiles_path
        self.profiles: list[Profile] = []
        self.selected_profile: Profile | None = None
    
    def construct(self) -> None:
        if not os.path.exists(self.profiles_path):
            f = open(self.profiles_path, "w")
            f.close()
            profiles_json = {}
        else:
            with open(self.profiles_path, "rb") as f:
                data = f.read()
            try:
                profiles_json: dict[str, str] = json.loads(data)
            except json.JSONDecodeError:
                raise ProfileError("Invalid profile file!")
        
        for name, account_id in profiles_json.items():
            if not isinstance(name, str) or not isinstance(account_id, str):
                continue
            if len(name) > Profile.MAX_NAME_LENGTH or not checkid(account_id):
                continue

            p = Profile(name, account_id.lower())
            self.profiles.append(p)
        self.update()

    def update(self) -> None:
        d = {}
        for p in self.profiles:
            d[p.name] = p.account_id.lower()
        with open(self.profiles_path, "w") as f:
            json.dump(d, f)

    def create(self, p: Profile) -> None:
        self.profiles.append(p)
        self.update()
    
    def delete(self, p: Profile) -> None:
        self.profiles.remove(p)
        self.update()

    def delete_all(self) -> None:
        self.profiles = []
        self.update()

    def search_name(self, name: str) -> Profile | None:
        for p in self.profiles:
            if p.name == name:
                return p
        return None
    
    def select_profile(self, p: Profile) -> None:
        self.selected_profile = p
        
    def is_selected(self) -> bool:
        return bool(self.selected_profile)
    
    def is_empty(self) -> bool:
        return len(self.profiles) == 0
    
class Logger:
    def __init__(self, dimensions: tuple[int, int] = (200, 150)) -> None:
        self.text = ""
        with ui.scroll_area().classes(f"w-{dimensions[0]} h-{dimensions[1]} border") as scroll_area:
            self.scroll_area = scroll_area
            self.obj = ui.markdown().classes("w-full")

    def update_obj(self) -> None:
        self.obj.set_content(self.text)

    def clear(self) -> None:
        self.text = ""
        self.update_obj()
    
    def write(self, prefix: str | None, msg: str) -> None:
        if prefix:
            self.text += f"\n\n{prefix} {msg}"
        else:
            self.text += f"\n\n{msg}"
        self.update_obj()

    def info(self, msg: str) -> None:
        self.write("[INFO]", msg)

    def warning(self, msg: str) -> None:
        self.write("[WARNING]", msg)

    def error(self, msg: str) -> None:
        self.write("[ERROR]", msg)

    def exception(self, msg: str) -> None:
        msg = f"```{traceback.format_exc()}```\n\n{msg}"
        self.write("[EXCEPTION]", msg)

    def hide(self) -> None:
        self.obj.set_visibility(False)
        self.scroll_area.set_visibility(False)
    
    def show(self) -> None:
        self.obj.set_visibility(True)
        self.scroll_area.set_visibility(True)

class SettingObject(Enum):
    CHECKBOX = auto()

class SettingKey:
    def __init__(self, default_value: Any, obj: SettingObject, key: str, desc: str, value: Any | None = None, validator: Callable[[Any], bool] | None = None) -> None:
        match obj:
            case SettingObject.CHECKBOX:
                self.type = bool
        if validator is None:
            self.validator = lambda _: True
        else:
            self.validator = validator

        assert isinstance(default_value, self.type)
        assert self.validator(default_value)
        self.default_value = default_value

        if value is None:
            self._value = self.default_value
        else:
            self.value = value

        self.obj = obj
        self.key = key
        self.desc = desc

    @property
    def value(self) -> Any:
        return self._value
    
    @value.setter
    def value(self, value: Any) -> None:
        if not isinstance(value, self.type):
            raise SettingsError(f"Invalid type (expected {self.type}, got {type(value)})!")
        if not self.validator(value):
            raise SettingsError("Invalid value!")
        self._value = value

class Settings:
    recursivity = SettingKey(
        False, SettingObject.CHECKBOX, "recursivity", "Recursively search for input files where applicable"
    )
    settings_map = {
        recursivity.key: recursivity
    }
    settings = settings_map.values()

    def __init__(self, settings_path: str) -> None:
        self.settings_path = settings_path

    def construct(self) -> None:
        if not os.path.exists(self.settings_path):
            f = open(self.settings_path, "w")
            f.close()
            settings_json = {}
        else:
            with open(self.settings_path, "rb") as f:
                data = f.read()
            try:
                settings_json: dict[str, Any] = json.loads(data)
            except json.JSONDecodeError:
                raise SettingsError("Invalid settings file!")

        for k, v in settings_json.items():
            s = self.settings_map.get(k)
            if s:
                s.value = v
        self.update()

    def update(self) -> None:
        d = {}
        for k, v in self.settings_map.items():
            d[k] = v.value
        with open(self.settings_path, "w") as f:
            json.dump(d, f)

class TabBase:
    def __init__(self, name: str, profiles: Profiles | None, settings: Settings | None) -> None:
        self.profiles = profiles
        self.settings = settings
        self.tab = ui.tab(name)
        self.in_folder = ""
        self.out_folder = ""
    
    def construct(self) -> None:
        with ui.row():
            self.input_button = ui.button("Select folder of savefiles", on_click=self.on_input)
            self.in_label = ui.markdown()
        with ui.row():
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.markdown()
        self.start_button = ui.button("Start", on_click=self.on_start)
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
    
    def disable_buttons(self) -> None:
        self.input_button.disable()
        self.output_button.disable()
        self.start_button.disable()
    
    def enable_buttons(self) -> None:
        self.input_button.enable()
        self.output_button.enable()
        self.start_button.enable()