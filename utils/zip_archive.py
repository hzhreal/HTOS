import asyncio
import os
from zipfile import ZipFile, BadZipFile
from zipfile import (
    #ZIP_BZIP2,
    #ZIP_DEFLATED,
    #ZIP_LZMA,
    ZIP_STORED
)
from utils.constants import (
    MAX_FILES, GENERAL_CHUNKSIZE, SAVESIZE_MAX,
    MAX_FILENAME_LEN, MAX_PATH_LEN,
    MANDATORY_SCE_SYS_CONTENTS, SYS_FILE_MAX, SCE_SYS_NAME, SAVEBLOCKS_MAX
)
from utils.orbis import get_path_len, compute_saveblocks
from utils.conversions import gb_to_bytes, bytes_to_mb
from utils.exceptions import FileError 

ZIP_COMPRESSION_MODE = ZIP_STORED
ZIP_COMPRESSION_LEVEL = None
def _zip_pack(src_dir: str, dst_name: str) -> None:
    dst = os.path.join(src_dir, dst_name)
    with ZipFile(dst, "w", compression=ZIP_COMPRESSION_MODE, compresslevel=ZIP_COMPRESSION_LEVEL) as zf:
        # crawling through directory and subdirectories
        for dirpath, _, filenames in os.walk(src_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.abspath(filepath) == os.path.abspath(dst):
                    continue
                archive_path = os.path.relpath(filepath, src_dir)
                # writing each file one by one without the top-level folder
                zf.write(filepath, archive_path)

async def zip_pack(src_dir: str, dst_name: str) -> None:
    await asyncio.to_thread(_zip_pack, src_dir, dst_name)

ZIP_TOTAL_SIZE_LIMIT = gb_to_bytes(2)
ZIP_SAVEGAME_MAX = SAVESIZE_MAX
ZIP_CHUNKSIZE = GENERAL_CHUNKSIZE
ZIP_MAX_ENTRIES = MAX_FILES
ZIP_MAX_NESTED_DIRS = 100
ZIP_MANDATORY_SCE_SYS_FILES = frozenset([os.path.join(SCE_SYS_NAME, a) for a in MANDATORY_SCE_SYS_CONTENTS])
def _zip_unpack(src_file: str, dst_dir: str) -> int:
    dst_dir = os.path.realpath(dst_dir)
    total_size = 0
    mandatory_cnt = 0
    with ZipFile(src_file, "r") as zf:
        il = zf.infolist()
        if len(il) > ZIP_MAX_ENTRIES:
            raise FileError(
                "The amount of entries in the archive excceds "
                f"{ZIP_MAX_ENTRIES}!"
            )
        for i in il:
            fn = i.filename
            fs = i.file_size

            out_p = os.path.join(dst_dir, fn)
            out_p = os.path.realpath(out_p)
            if os.path.commonpath([dst_dir, out_p]) != dst_dir:
                raise FileError("Invalid ZIP archive!")
            out_rel_p = os.path.relpath(out_p, dst_dir)

            if i.is_dir():
                nest_cnt = len(out_rel_p.split(os.sep))
                if nest_cnt > ZIP_MAX_NESTED_DIRS:
                    raise FileError(
                        "A directory in the archive exceeds the nesting limit of "
                        f"{ZIP_MAX_NESTED_DIRS}!"
                    )

                path_len = get_path_len(out_rel_p)
                if path_len > MAX_PATH_LEN:
                    raise FileError(
                        "A directory in the archive will turn out to "
                        "exceed the path length limit!"
                    )

                continue

            if fs > ZIP_SAVEGAME_MAX:
                raise FileError(
                    f"A file in archive exceeds file size limit "
                    f"{bytes_to_mb(SAVESIZE_MAX)} MB!"
                )

            if total_size + fs > ZIP_TOTAL_SIZE_LIMIT:
                raise FileError(
                    "Archive exceeds total unpacked size limit "
                    f"{bytes_to_mb(ZIP_TOTAL_SIZE_LIMIT)} MB!"
                )
            total_size += fs

            dn = os.path.dirname(out_rel_p)
            nest_cnt = len(dn.split(os.sep))
            if nest_cnt > ZIP_MAX_NESTED_DIRS:
                raise FileError(
                    "A directory in the archive exceeds the nesting limit of "
                    f"{ZIP_MAX_NESTED_DIRS}!"
                )
            dn = os.path.dirname(out_p)

            path_len = get_path_len(out_rel_p)
            if path_len > MAX_PATH_LEN:
                raise FileError(
                    "A file in the archive will turn out to exceed "
                    "the path length limit!"
                )

            bn = os.path.basename(out_rel_p)
            if len(bn) > MAX_FILENAME_LEN:
                raise FileError(
                    "A file in the archive exceeds the maximum file name length of "
                    f"{MAX_FILENAME_LEN}!"
                )

            if out_rel_p in ZIP_MANDATORY_SCE_SYS_FILES:
                if fs > SYS_FILE_MAX:
                    raise FileError(
                        "A sce_sys file in the archive exceeds the "
                        "respective max size!"
                    )
                mandatory_cnt += 1
        if mandatory_cnt != len(ZIP_MANDATORY_SCE_SYS_FILES):
            raise FileError(
                "Archive is missing mandatory sce_sys files!"
            )
        saveblocks = compute_saveblocks(total_size)
        if saveblocks > SAVEBLOCKS_MAX:
            raise FileError(
                "Unpacked archive will exceed max size!"
            )

        for i in il:
            fn = i.filename
            fs = i.file_size

            out_p = os.path.join(dst_dir, fn)
            out_p = os.path.realpath(out_p)

            if i.is_dir():
                if not os.path.exists(out_p):
                    os.makedirs(out_p)
                continue

            dn = os.path.dirname(out_p)
            if not os.path.exists(dn):
                os.makedirs(dn)

            entry_size = 0
            with zf.open(i, "r") as src, open(out_p, "wb") as dst:
                while True:
                    chunk = src.read(ZIP_CHUNKSIZE)
                    if not chunk:
                        break
                    l = len(chunk)

                    entry_size += l
                    if entry_size > fs:
                        raise FileError("Invalid archive!")

                    dst.write(chunk)

    return saveblocks

async def zip_unpack(src_file: str, dst_dir: str) -> int:
    try:
        return await asyncio.to_thread(_zip_unpack, src_file, dst_dir)
    except BadZipFile:
        raise FileError("Invalid archive!")

