from functools import partial

from nicegui import ui, app
from nicegui.events import ValueChangeEventArguments
from webview import FileDialog

from app_core.models import SettingObject, SettingKey, Settings
from app_core.exceptions import SettingsError

class SettingSelector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            self.settings.construct()
        except SettingsError as e:
            ui.notify(e)
        self.widgets = {}

        self.tab = ui.tab("Settings")

    def construct(self) -> None:
        for v in self.settings.settings:
            match v.obj:
                case SettingObject.CHECKBOX:
                    ui.checkbox(v.desc, value=v.value, on_change=partial(self.on_change, v))
                case SettingObject.FOLDERSELECT:
                    with ui.row().style("align-items: center"):
                        ui.button(v.desc, on_click=partial(self.folder_dialog, v))
                        self.widgets[v.key] = ui.input(on_change=lambda e: v.set_value_safe(e.value), value=v.value)

    def on_change(self, s: SettingKey, event: ValueChangeEventArguments) -> None:
        try:
            s.value = event.value
            self.settings.update()
        except SettingsError as e:
            ui.notify(e)

    async def folder_dialog(self, v: SettingKey) -> None:
        folder = await app.native.main_window.create_file_dialog(dialog_type=FileDialog.FOLDER)
        if folder:
            v.value = folder[0]
            md: ui.input = self.widgets[v.key]
            md.set_value(v.value)
            self.settings.update()