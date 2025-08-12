from __future__ import annotations

import os
import json
import traceback

from nicegui import ui

from utils.orbis import checkid
from app_core.exceptions import ProfileError

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