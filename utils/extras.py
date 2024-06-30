import os
import zipfile
import random
import string
import aiofiles.os
from PIL import Image
from utils.constants import logger, ZIPFILE_COMPRESSION_MODE, ZIPFILE_COMPRESSION_LEVEL

def zipfiles(directory_to_zip: str, zip_file_name: str) -> None:

    def get_all_file_paths(directory: str) -> list[tuple[str, str]]: 
  
        # initializing empty file paths list 
        file_paths = [] 
    
        # crawling through directory and subdirectories 
        for root, _, files in os.walk(directory): 
            for filename in files: 
                # join the two strings in order to form the full filepath.
                filepath = os.path.join(root, filename)
                file_paths.append((root, filepath))  # Store both the root and the full file path
    
        # returning all file paths 
        return file_paths    

    file_paths = get_all_file_paths(directory_to_zip) 
    full_new_path = os.path.join(directory_to_zip, zip_file_name)
  
    # writing files to a zipfile 
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

        if image.mode != "RGB":
            image = image.convert("RGB")

        image = image.resize(size)
        image.save(path)

        image.close()
    except Exception as e:
        logger.exception(f"Error processing {path}: {e} - (unexpected)")

async def obtain_savenames(dir_: str) -> list[str]:
    savenames = []
    saves = await aiofiles.os.listdir(dir_)

    for fileName in saves:
        if not fileName.endswith(".bin"):
            savenames.append(fileName)
    return savenames
