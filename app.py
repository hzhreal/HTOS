import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

import argparse
from nicegui import ui

from app_core import models
from app_core.profile_selector import ProfileSelector
from app_core.setting_selector import SettingSelector
from app_core.resign import Resign
from app_core import Decrypt
from utils.constants import APP_PROFILES_PATH, APP_SETTINGS_PATH
from utils.workspace import WorkspaceOpt, startup

workspace_opt = WorkspaceOpt()
profiles = models.Profiles(APP_PROFILES_PATH)
settings = models.Settings(APP_SETTINGS_PATH)

def initialize_tabs() -> None:
    with ui.tabs().classes("w-full") as tabs:
        p_s = ProfileSelector(profiles)
        r = Resign(profiles)
        d = Decrypt()
        s_s = SettingSelector(settings)
    with ui.tab_panels(tabs, value=p_s.tab).classes("w-full"):
        with ui.tab_panel(p_s.tab):
            p_s.construct()
        with ui.tab_panel(r.tab):
            r.construct()
        with ui.tab_panel(d.tab):
            d.construct()
        with ui.tab_panel(s_s.tab):
            s_s.construct()

if __name__ in {"__main__", "__mp_main__"}:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore-startup", action="store_true")
    args = parser.parse_args()
    if args.ignore_startup:
        workspace_opt.ignore_startup = True
    startup(workspace_opt, lite=True)

    ui.dark_mode().enable()
    initialize_tabs()
    ui.run(native=True, window_size=(200, 200))