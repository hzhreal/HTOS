import os
import shutil
from aiofiles.os import mkdir, listdir
from aiofiles.ospath import exists, isfile, getsize

from data.crypto.common import CustomCrypto as CC
from app_core.models import Logger, Settings
from utils.constants import PS_UPLOADDIR, MAX_FILENAME_LEN, MAX_PATH_LEN, RANDOMSTRING_LENGTH
from utils.orbis import OrbisError, parse_pfs_header, parse_sealedkey
from utils.extras import FileError
from utils.extras import generate_random_string

async def get_files_nonrecursive(folder_path: str) -> list[str]:
    files = []
    for path in await listdir(folder_path):
        if await isfile(path):
            files.append(path)
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
        files = await CC.obtainFiles(folder_path)
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
        files = await CC.obtainFiles(folder_path)
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
        files = CC.obtainFiles(folder_path)
    else:
        files = get_files_nonrecursive(folder_path)

    size = 0
    for f in files:
        size += await getsize(f)
    return size, files