import os
import zipfile
import random
import string
from PIL import Image, UnidentifiedImageError
from utils.constants import ZIPFILE_COMPRESSION_MODE, ZIPFILE_COMPRESSION_LEVEL, EMBED_DESC_LIM
from utils.exceptions import FileError

def zipfiles(directory_to_zip: str, zip_file_name: str) -> None:

    def get_all_file_paths(directory: str) -> list[tuple[str, str]]: 
        file_paths = [] 

        # crawling through directory and subdirectories 
        for root, _, files in os.walk(directory): 
            for filename in files: 
                filepath = os.path.join(root, filename)
                file_paths.append((root, filepath))

        return file_paths

    file_paths = get_all_file_paths(directory_to_zip) 
    full_new_path = os.path.join(directory_to_zip, zip_file_name)

    with zipfile.ZipFile(full_new_path, 'w', compression=ZIPFILE_COMPRESSION_MODE, compresslevel=ZIPFILE_COMPRESSION_LEVEL) as f: 
       # writing each file one by one without the top-level folder
        for _, file in file_paths:
            archive_name = os.path.relpath(file, directory_to_zip)
            f.write(file, archive_name)

def generate_random_string(length: int) -> str:
    characters = string.ascii_letters + string.digits
    random_string = "".join(random.choice(characters) for _ in range(length))
    return random_string

def pngprocess(path: str, size: tuple[int, int]) -> None:
    try:
        image = Image.open(path)
    except UnidentifiedImageError:
        raise FileError("Failed to open image!")

    if image.mode != "RGB":
        image = image.convert("RGB")

    image = image.resize(size)
    image.save(path)

    image.close()

async def obtain_savenames(saves: list[str]) -> list[str]:
    savenames = []
    for i in range(0, len(saves), 2):
        path = saves[i]
        base = path.removesuffix(".bin")
        savenames.append(base)
    return savenames

def completed_print(savenames: list[str], pos: int = EMBED_DESC_LIM // 4) -> str:
    assert pos > 0

    savenames = [os.path.basename(x) for x in savenames]

    if len(savenames) == 1:
        return savenames[0]

    delim = ", "
    finished_files = delim.join(savenames)
    strlen = len(finished_files)
    i = len(savenames) - 1
    while strlen > pos and pos != 0:
        strlen -= (len(savenames[i]) + len(delim))
        finished_files = finished_files[:strlen]
        i -= 1
    if i != len(savenames) - 1:
        finished_files += ", ..."

    return finished_files
