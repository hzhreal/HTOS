import os
import random
import string
from PIL import Image, UnidentifiedImageError
from utils.constants import EMBED_DESC_LIMIT
from utils.exceptions import FileError

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

def completed_print(savenames: list[str], pos: int = EMBED_DESC_LIMIT // 4) -> str:
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

