import os
import shutil
from aiofiles.os import mkdir, listdir
from aiofiles.ospath import exists, isfile, isdir, getsize

from app_core.models import Logger, Settings
from utils.constants import PS_UPLOADDIR, MAX_FILENAME_LEN, MAX_PATH_LEN, RANDOMSTRING_LENGTH, SAVEBLOCKS_MIN, SAVEBLOCKS_MAX
from utils.orbis import OrbisError, parse_pfs_header, parse_sealedkey
from utils.extras import FileError
from utils.extras import generate_random_string

async def get_files_nonrecursive(folder_path: str) -> list[str]:
    files = []
    for basename in await listdir(folder_path):
        full_path = os.path.join(folder_path, basename)
        if await isfile(full_path):
            files.append(full_path)
    return files

async def get_files_recursive(folder: str, files: list[str] | None = None) -> list[str]:
    if files is None:
        files = []

    filelist = await listdir(folder)

    for entry in filelist:
        entry_path = os.path.join(folder, entry)

        if await isfile(entry_path):
            files.append(entry_path)
        elif await isdir(entry_path):
            await get_files_recursive(entry_path, files)
    return files

def save_pair_check(logger: Logger, paths: list[str], savepair_limit: int | None) -> list[str]:
    valid_files_temp = []
    for file in paths:
        filename = os.path.basename(file) + f"_{'X' * RANDOMSTRING_LENGTH}"
        filename_len = len(filename)
        path = PS_UPLOADDIR + "/" + filename + "/"
        path_len = len(path)

        if filename_len > MAX_PATH_LEN:
            logger.warning(f"Filename {filename} ({filename_len}) will exceed {MAX_FILENAME_LEN}. Skipping...")
            continue
        if path_len > MAX_PATH_LEN:
            logger.warning(f"Path {path} ({path_len}) will exceed {MAX_FILENAME_LEN}. Skipping...")
            continue
        valid_files_temp.append(file)

    valid_files = []
    for file in valid_files_temp:
        filename = os.path.basename(file)
        if filename.endswith(".bin"):
            # look for pair
            for file_nested in valid_files_temp:
                filename_nested = os.path.basename(file_nested)
                if filename_nested == filename:
                    continue

                # pair found
                if filename_nested == os.path.splitext(filename)[0]:
                    valid_files.append(file)
                    valid_files.append(file_nested) 

    valid_files_cnt = len(valid_files)
    savepair_cnt = valid_files_cnt / 2
    if valid_files_cnt == 0:
        raise OrbisError("No valid saves found!")
    if savepair_limit and savepair_cnt > savepair_limit:
        raise FileError(f"Maximum savepair limit of {savepair_limit} exceeded ({savepair_cnt})!")

    return valid_files

async def prepare_save_input_folder(settings: Settings, logger: Logger, folder_path: str, output_folder_path: str, savepair_limit: int | None = None) -> list[list[str]]:
    finished_files = []

    if settings.recursivity.value:
        files = await get_files_recursive(folder_path)
    else:
        files = await get_files_nonrecursive(folder_path)
    saves = save_pair_check(logger, files, savepair_limit)

    # no files in output root, only folder for each batch
    cur_output_dir = os.path.join(output_folder_path, os.path.basename(output_folder_path))
    await mkdir(cur_output_dir)

    finished_files_cycle = []
    for file in saves:
        # quick check first
        if file.endswith(".bin"):
            await parse_sealedkey(file)
        else:
            await parse_pfs_header(file)

        filename = os.path.basename(file)
        filepath_out = os.path.join(cur_output_dir, filename)
        if await exists(filepath_out):
            cur_output_dir = os.path.join(output_folder_path, generate_random_string(RANDOMSTRING_LENGTH))
            await mkdir(cur_output_dir)
            filepath_out = os.path.join(cur_output_dir, filename)
            finished_files.append(finished_files_cycle)
            finished_files_cycle = []

        shutil.copyfile(file, filepath_out)
        finished_files_cycle.append(filepath_out)
    finished_files.append(finished_files_cycle)
    return finished_files

async def prepare_files_input_folder(settings: Settings, folder_path: str, output_folder_path: str) -> list[list[str]]:
    finished_files = []

    if settings.recursivity.value:
        files = await get_files_recursive(folder_path)
    else:
        files = await get_files_nonrecursive(folder_path)

    cur_output_dir = os.path.join(output_folder_path, os.path.basename(output_folder_path))
    await mkdir(cur_output_dir)

    finished_files_cycle = []
    for file in files:
        filename = os.path.basename(file)
        filepath_out = os.path.join(cur_output_dir, filename)
        if await exists(filepath_out):
            cur_output_dir = os.path.join(output_folder_path, generate_random_string(RANDOMSTRING_LENGTH))
            await mkdir(cur_output_dir)
            filepath_out = os.path.join(cur_output_dir, filename)
            finished_files.append(finished_files_cycle)
            finished_files_cycle = []

        shutil.copyfile(file, filepath_out)
        finished_files_cycle.append(filepath_out)
    finished_files.append(finished_files_cycle)
    return finished_files

async def calculate_foldersize(settings: Settings, folder_path: str) -> tuple[int, list[str]]:
    if settings.recursivity.value:
        files = await get_files_recursive(folder_path)
    else:
        files = await get_files_nonrecursive(folder_path)

    size = 0
    for f in files:
        size += await getsize(f)
    return size, files

async def check_save(path: str) -> tuple[bool, tuple[str, str]]:
    if path.endswith(".bin"):
        savefile = path.removesuffix(".bin")
        binfile = path
    else:
        savefile = path
        binfile = path + ".bin"

    if not await isfile(savefile) or not await isfile(binfile):
        return False, ("", "")
    try:
        await parse_sealedkey(binfile)
        await parse_pfs_header(savefile)
    except OrbisError:
        return False, ("", "")
    return True, (savefile, binfile)

async def prepare_single_save_folder(savepair: tuple[str, str], output_folder_path: str) -> tuple[str, str]:
    output_dir = os.path.join(output_folder_path, os.path.basename(output_folder_path))
    await mkdir(output_dir)

    outpair = []
    for file in savepair:
        filename = os.path.basename(file)
        filepath_out = os.path.join(output_dir, filename)
        shutil.copyfile(file, filepath_out)
        outpair.append(filepath_out)
    return tuple(outpair)

def int_validation(s: str | int, min_: int, max_: int) -> bool:
    assert min_ < max_
    if type(s) == str and s.lower().startswith("0x"):
        s = s[2:]
        try:
            n = int(s, 16)
        except ValueError:
            return False
    else:
        try:
            n = int(s)
        except ValueError:
            return False
    return min_ <= n <= max_
