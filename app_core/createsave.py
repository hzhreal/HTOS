import os

from nicegui import ui
from aiofiles.os import makedirs
from aiofiles.ospath import isdir

from app_core.models import Profiles, Settings, TabBase, Logger
from app_core.helpers import int_validation, calculate_foldersize, get_files_nonrecursive
from data.crypto.helpers import extra_import
from network.socket_functions import C1socket 
from network.ftp_functions import FTPps 
from network.exceptions import SocketError, FTPError
from utils.constants import IP, PORT_FTP, PS_UPLOADDIR, SAVEBLOCKS_MIN, SAVEBLOCKS_MAX, SAVESIZE_MB_MIN, SAVESIZE_MB_MAX, RANDOMSTRING_LENGTH, MAX_FILENAME_LEN, MAX_PATH_LEN, SCE_SYS_NAME, PARAM_NAME, CREATESAVE_ENC_CHECK_LIMIT, SCE_SYS_CONTENTS, RANDOMSTRING_LENGTH, MOUNT_LOCATION, PS_UPLOADDIR
from utils.workspace import cleanup
from utils.orbis import validate_savedirname, sys_files_validator, sfo_ctx_create, sfo_ctx_write, sfo_ctx_patch_parameters, obtainCUSA
from utils.exceptions import OrbisError
from utils.conversions import mb_to_saveblocks, saveblocks_to_bytes, bytes_to_mb
from utils.namespaces import Crypto
from utils.extras import generate_random_string

class Createsave(TabBase):
    def __init__(self, profiles: Profiles, settings: Settings) -> None:
        super().__init__("Createsave", profiles, settings)

    def construct(self) -> None:
        with ui.row().style("align-items: center"):
            self.input_button = ui.button("Select folder of files", on_click=self.on_input)
            self.in_label = ui.input(on_change=self.on_input_label, value=self.in_folder).props("clearable")
        with ui.row().style("align-items: center"):
            self.output_button = ui.button("Select output folder", on_click=self.on_output)
            self.out_label = ui.input(on_change=self.on_output_label, value=self.out_folder).props("clearable")
        self.savename = ui.input(
            "savename",
            validation={"Invalid savename!": validate_savedirname}
        ).classes("w-64").props("clearable")
        self.saveblocks = ui.input(
            "Savesize (saveblocks) (priority)",
            validation={"Invalid savesize!": lambda s: int_validation(s, SAVEBLOCKS_MIN, SAVEBLOCKS_MAX)}
        ).classes("w-64").props("clearable")
        self.savesize_mb = ui.input(
            "Savesize (MB)",
            validation={"Invalid savesize!": lambda s: int_validation(s, SAVESIZE_MB_MIN, SAVEBLOCKS_MIN)}
        ).classes("w-64").props("clearable")
        self.ignore_secondlayer_checks_checkbox = ui.checkbox("Ignore secondlayer checks")
        self.start_button = ui.button("Start", on_click=self.on_start)
        self.logger = Logger(self.settings)

    async def on_start(self) -> None:
        # saveblocks takes priority
        if int_validation(self.saveblocks.value, SAVEBLOCKS_MIN, SAVEBLOCKS_MAX):
            if type(self.saveblocks.value) == str and self.saveblocks.value.lower().startswith("0x"):
                saveblocks = int(self.saveblocks.value[2:], 16)
            else:
                saveblocks = int(self.saveblocks.value)
            savesize = saveblocks_to_bytes(saveblocks)
            self.savesize_mb.set_value(bytes_to_mb(savesize))
        elif int_validation(self.savesize_mb.value, SAVESIZE_MB_MIN, SAVESIZE_MB_MAX):
            if type(self.savesize_mb.value) == str and self.savesize_mb.value.lower().startswith("0x"):
                saveblocks = mb_to_saveblocks(int(self.savesize_mb.value[2:], 16))
            else:
                saveblocks = mb_to_saveblocks(int(self.savesize_mb.value))
            savesize = saveblocks_to_bytes(saveblocks)
            self.saveblocks.set_value(saveblocks)
        else:
            ui.notify("Savesize is not set!")
            return
        if not validate_savedirname(self.savename.value):
            ui.notify("Arguments are not set!")
            return
        else:
            savename = self.savename.value
        ignore_secondlayer_checks = self.ignore_secondlayer_checks_checkbox.value

        if not await self.validation():
            ui.notify("Invalid paths!")
            return
        if not self.profiles.is_selected():
            ui.notify("No profile selected!")
            return
        self.disable_buttons()

        p = self.profiles.selected_profile.copy()

        self.logger.clear()
        self.logger.info("Creating save...")

        C1ftp = FTPps(IP, PORT_FTP, PS_UPLOADDIR, "", "", "",
                    self.out_folder, "", "", "")
        mount_paths = []
        save = []
        sys_folder = os.path.join(self.in_folder, SCE_SYS_NAME)
        rand_str = generate_random_string(RANDOMSTRING_LENGTH)
        
        try:
            # size check
            foldersize, files = await calculate_foldersize(self.settings, self.in_folder)
            if foldersize > savesize:
                raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")

            # length checks
            filename_bin = f"{savename}.bin_{'X' * RANDOMSTRING_LENGTH}"
            filename_bin_len = len(filename_bin)
            path_len = len(PS_UPLOADDIR + "/" + filename_bin + "/")

            if filename_bin_len > MAX_FILENAME_LEN:
                raise OrbisError(f"The length of the savename will exceed {MAX_FILENAME_LEN}!")
            elif path_len > MAX_PATH_LEN:
                raise OrbisError(f"The path the save creates will exceed {MAX_PATH_LEN}!")
            
            if not await isdir(sys_folder):
                raise OrbisError("No sce_sys folder found!")
            sys_files = await get_files_nonrecursive(sys_folder)
            sys_files_validator(sys_files)
            sfo_path = os.path.join(sys_folder, PARAM_NAME)

            sfo_ctx = await sfo_ctx_create(sfo_path)
            sfo_ctx_patch_parameters(sfo_ctx, ACCOUNT_ID=p.account_id, SAVEDATA_DIRECTORY=savename, SAVEDATA_BLOCKS=saveblocks)
            title_id = obtainCUSA(sfo_ctx)
            await sfo_ctx_write(sfo_ctx, sfo_path)

            if len(files) <= CREATESAVE_ENC_CHECK_LIMIT and not ignore_secondlayer_checks: # dont want to create unnecessary overhead
                self.logger.info("Doing second layer checks...")
                for gamesave in files:
                    if os.path.basename(gamesave) in SCE_SYS_CONTENTS:
                        continue
                    await extra_import(Crypto, title_id, gamesave)

            temp_savename = savename + f"_{rand_str}"
            mount_location_new = MOUNT_LOCATION + "/" + rand_str
            location_to_scesys = mount_location_new + f"/{SCE_SYS_NAME}"

            self.logger.info(f"Creating {savename} ({title_id}) ({saveblocks} blocks) ({p}).")
            await C1socket.socket_createsave(PS_UPLOADDIR, temp_savename, saveblocks)
            save.extend([temp_savename, f"{savename}_{rand_str}.bin"])
            mount_paths.append(mount_location_new)
            await C1ftp.make1(mount_location_new)
            await C1ftp.make1(location_to_scesys)
            await C1socket.socket_dump(mount_location_new, temp_savename)
            if self.settings.recursivity.value:
                await C1ftp.upload_folder(mount_location_new, self.in_folder)
            else:
                ftp = await C1ftp.create_ctx()
                for sys_file in sys_files:
                    remote_path = os.path.join(location_to_scesys, os.path.basename(sys_file))
                    await C1ftp.uploadStream(ftp, sys_file, remote_path)
                for file in files:
                    remote_path = os.path.join(mount_location_new, os.path.basename(file))
                    await C1ftp.uploadStream(ftp, file, remote_path)
                await C1ftp.free_ctx(ftp)
            await C1socket.socket_update(mount_location_new, temp_savename)
            
            # make paths for save
            out_folder = os.path.join(self.out_folder, rand_str)
            save_dirs = os.path.join(out_folder, "PS4", "SAVEDATA", p.account_id, title_id)
            await makedirs(save_dirs)

            # download save at real filename path
            ftp_ctx = await C1ftp.create_ctx()
            await C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename, os.path.join(save_dirs, savename)),
            await C1ftp.downloadStream(ftp_ctx, PS_UPLOADDIR + "/" + temp_savename + ".bin", os.path.join(save_dirs, savename + ".bin"))
            await C1ftp.free_ctx(ftp_ctx)
        except (SocketError, FTPError, OrbisError, OSError) as e:
            await cleanup(C1ftp, None, save, mount_paths)
            self.logger.error(f"`{str(e)}` Stopping...")
            self.enable_buttons()
            return
        except Exception:
            await cleanup(C1ftp, None, save, mount_paths)
            self.logger.exception("Unexpected error. Stopping...")
            self.enable_buttons()
            return

        await cleanup(C1ftp, None, save, mount_paths)
        self.logger.info(f"Created {savename} ({title_id}) ({saveblocks} blocks) ({p}).")
        self.logger.info(f"Save can be found at ```{out_folder}```.")
        self.logger.info("Done!")
        self.enable_buttons()

    def disable_buttons(self) -> None:
        super().disable_buttons()
        self.savename.disable()
        self.saveblocks.disable()
        self.savesize_mb.disable()
        self.ignore_secondlayer_checks_checkbox.disable()
    
    def enable_buttons(self) -> None:
        super().enable_buttons()
        self.savename.enable()
        self.saveblocks.enable()
        self.savesize_mb.enable()
        self.ignore_secondlayer_checks_checkbox.enable()
