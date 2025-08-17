import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

import argparse
from nicegui import ui

from app_core import models
from app_core.profile_selector import ProfileSelector
from app_core.setting_selector import SettingSelector
from app_core.resign import Resign
from app_core.encrypt import Encrypt
from app_core.decrypt import Decrypt
from app_core.reregion import Reregion
from utils.constants import APP_PROFILES_PATH, APP_SETTINGS_PATH
from utils.workspace import WorkspaceOpt, startup

workspace_opt = WorkspaceOpt()
profiles = models.Profiles(APP_PROFILES_PATH)
settings = models.Settings(APP_SETTINGS_PATH)

def initialize_tabs() -> None:
    with ui.tabs().classes("w-full") as tabs:
        tab_container = [
            ProfileSelector(profiles),
            Resign(profiles, settings),
            Decrypt(settings),
            Encrypt(profiles, settings),
            Reregion(profiles, settings),
            SettingSelector(settings)
        ]
    with ui.tab_panels(tabs, value=tab_container[0].tab).classes("w-full"):
        for t in tab_container:
            with ui.tab_panel(t.tab):
                t.construct()

if __name__ in {"__main__", "__mp_main__"}:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore-startup", action="store_true")
    args = parser.parse_args()
    if args.ignore_startup:
        workspace_opt.ignore_startup = True
    startup(workspace_opt, lite=True)

    ui.dark_mode().enable()
    initialize_tabs()
    ui.run(native=True, window_size=(500, 500))