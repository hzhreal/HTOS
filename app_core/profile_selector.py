from nicegui import ui
from nicegui.events import ValueChangeEventArguments
from functools import partial

from app_core.models import Profiles, Profile
from app_core.exceptions import ProfileError

from utils.orbis import checkid

class ProfileSelector:
    def __init__(self, profiles: Profiles) -> None:
        self.profiles = profiles
        self.p = Profile() # hold current created profile
        try:
            self.profiles.construct()
        except ProfileError as e:
            ui.notify(e)

        self.tab = ui.tab("Profile selector")

    def construct(self) -> None:
        self.list_container = ui.list()
        with ui.dialog() as dialog, ui.card():
            self.dialog = dialog
            i_name = ui.input(
                label="Name",
                validation={f"Max length is {Profile.MAX_NAME_LENGTH}!": self.check_name},
                on_change=self.on_set_name
            ).props("clearable")
            i_accid = ui.input(
                label="Account ID", placeholder="0123456789ABCDEF",
                validation={"Invalid account ID": self.check_accid},
                on_change=self.on_set_accid
            ).props("clearable")
            ui.button("Create", on_click=partial(self.on_create, (i_name, i_accid)))
            ui.button("Close", on_click=partial(self.on_close_dialog, (i_name, i_accid), dialog))

        self.update_column()
    
    def update_column(self) -> None:
        self.list_container.clear()

        with self.list_container.props("bordered separator").classes("fixed-center"):
            with ui.item_section():
                ui.button("Delete all profiles", on_click=self.on_delete_all)
                ui.button("Create a profile", on_click=self.dialog.open).props("side")
            self.main_label = ui.item_label(
                "Click to select a profile:"
            ).props("header").classes("text-bold")
            ui.separator()

            for p in self.profiles.profiles:
                with ui.item(on_click=partial(self.on_select, p)):
                    with ui.item_section().props("avatar"):
                        ui.icon("person")
                    with ui.item_section():
                        ui.item_label(p.pad_name())
                        ui.item_label(p.account_id).props("caption")
                    with ui.item_section().props("side"):
                        ui.button("Delete", on_click=partial(self.on_delete, p))

    def check_accid(self, accid: str) -> bool:
        if not checkid(accid):
            self.p.account_id = ""
            return False
        return True
    
    def check_name(self, name: str) -> bool:
        return len(name) <= Profile.MAX_NAME_LENGTH

    def on_set_name(self, event: ValueChangeEventArguments) -> None:
        self.p.name = event.value

    def on_set_accid(self, event: ValueChangeEventArguments) -> None:
        self.p.account_id = event.value

    def on_select(self, p: Profile) -> None:
        self.profiles.select_profile(p)
        self.main_label.set_text(f"Selected: {p.name}")
        ui.notify(f"Selected {p}")

    def on_delete(self, p: Profile, silent: bool = False) -> None:
        self.profiles.delete(p)
        if not silent:
            ui.notify(f"Deleted {p}!")
        self.update_column()
    
    def on_delete_all(self) -> None:
        if self.profiles.is_empty():
            return
        self.profiles.delete_all()
        ui.notify("Deleted all profiles!")
        self.update_column()

    def on_create(self, inputs: tuple[ui.input, ...]) -> None:
        if self.p.is_set():
            p_match = self.profiles.search_name(self.p.name)
            if p_match:
                self.on_delete(p_match, silent=True)

            self.profiles.create(self.p)
            self.update_column()
            ui.notify(f"Created {self.p}")
            self.p = Profile()
            for i in inputs:
                i.set_value("")

    @staticmethod
    def on_close_dialog(inputs: tuple[ui.input, ...], dialog: ui.dialog) -> None:
        for i in inputs:
            i.set_value("")
        dialog.close()
