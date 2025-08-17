from __future__ import annotations

import os
import json
import traceback
from typing import Any, Callable
from enum import Enum, auto

from nicegui import ui

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
    def __init__(self) -> None:
        self.text = ""
        with ui.scroll_area().classes("w-200 h-150 border"):
            self.obj = ui.markdown().classes("w-full")

    def update_obj(self) -> None:
        self.obj.set_content(self.text)

    def clear(self) -> None:
        self.text = ""
        self.update_obj()
    
    def write(self, prefix: str, msg: str) -> None:
        self.text += f"\n\n{prefix} {msg}"
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