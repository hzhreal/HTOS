from functools import partial

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from app_core.models import SettingObject, SettingKey, Settings
from app_core.exceptions import SettingsError

class SettingSelector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            self.settings.construct()
        except SettingsError as e:
            ui.notify(e)

        self.tab = ui.tab("Settings")

    def construct(self) -> None:
        for v in self.settings.settings:
            match v.obj:
                case SettingObject.CHECKBOX:
                    ui.checkbox(v.desc, value=v.value, on_change=partial(self.on_change, v))

    def on_change(self, s: SettingKey, event: ValueChangeEventArguments) -> None:
        try:
            s.value = event.value
            self.settings.update()
        except SettingsError as e:
            ui.notify(e)