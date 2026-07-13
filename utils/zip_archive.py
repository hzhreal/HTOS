import asyncio
import os
from typing import Any
from zipfile import ZipFile, BadZipFile
from zipfile import (
    #ZIP_BZIP2,
    #ZIP_DEFLATED,
    #ZIP_LZMA,
    ZIP_STORED
)
from utils.constants import (
    MAX_FILES, GENERAL_CHUNKSIZE, SAVESIZE_MAX, SAVEBLOCKS_MAX,
    MAX_FILENAME_LEN, MAX_PATH_LEN, PARAM_NAME, SCE_SYS_NAME,
    MANDATORY_SCE_SYS_CONTENTS, SYS_FILE_MAX
)
from utils.orbis import get_path_len, compute_saveblocks
from utils.conversions import gb_to_bytes, bytes_to_mb
from utils.exceptions import FileError

ZIP_COMPRESSION_MODE = ZIP_STORED
ZIP_COMPRESSION_LEVEL = None
def _zip_pack(src_dir: str, dst_name: str) -> str:
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
    return dst
async def zip_pack(src_dir: str, dst_name: str) -> str:
    return await asyncio.to_thread(_zip_pack, src_dir, dst_name)

ZIP_TOTAL_SIZE_LIMIT = gb_to_bytes(2)
ZIP_SAVEGAME_MAX = SAVESIZE_MAX
ZIP_CHUNKSIZE = GENERAL_CHUNKSIZE
ZIP_MAX_ENTRIES = MAX_FILES
ZIP_MAX_NESTED_DIRS = 100
ZIP_MANDATORY_SCE_SYS_FILES = frozenset([os.path.join(SCE_SYS_NAME, a) for a in MANDATORY_SCE_SYS_CONTENTS])
ZIP_SFO_PATH = SCE_SYS_NAME + "/" + PARAM_NAME
class BoundedZipInfoCache(list):
    def append(self, object: Any) -> None:
        if len(self) >= ZIP_MAX_ENTRIES:
            raise FileError(
                f"Amount of entries in archive exceeds {ZIP_MAX_ENTRIES}!"
            )
        super().append(object)
class _ZipFile(ZipFile):
    def _RealGetContents(self) -> None:
        # prevent loading metadata for over ZIP_MAX_ENTRIES entries
        self.filelist = BoundedZipInfoCache()
        super()._RealGetContents()
def _zip_unpack(src_file: str, dst_dir: str) -> int:
    dst_dir = os.path.realpath(dst_dir)
    total_size = 0
    mandatory_cnt = 0
    out_fpaths = set()
    with _ZipFile(src_file, "r") as zf:
        il = zf.infolist()
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
                # assume directories inside save containers are case insensitive by default (which is the scope of this branch)
                # this should be a case insensitive check
                # that works on both case sensitive and case insensitive filesystems
                if out_rel_p.lower() in out_fpaths:
                    raise FileError("Duplicate entry found inside archive (case-insensitive check)!")
                out_fpaths.add(out_rel_p.lower())
                continue

            # assume files inside save containers are case insensitive by default (which is the scope of this branch)
            # this should be a case insensitive check
            # that works on both case sensitive and case insensitive filesystems
            if out_rel_p.lower() in out_fpaths:
                raise FileError("Duplicate entry found inside archive (case-insensitive check)!")

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

            out_fpaths.add(out_rel_p.lower())
        if mandatory_cnt != len(ZIP_MANDATORY_SCE_SYS_FILES):
            raise FileError(
                "Archive is missing mandatory sce_sys files!"
            )
        saveblocks = compute_saveblocks(total_size, len(il))
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
def _zip_unpack_sfo(src_file: str, dst_dir: str) -> str:
    out = os.path.join(dst_dir, PARAM_NAME)
    with _ZipFile(src_file, "r") as zf:
        try:
            sfo_info = zf.getinfo(ZIP_SFO_PATH)
        except KeyError:
            raise FileError("Invalid archive!")
        fs = sfo_info.file_size
        if fs > SYS_FILE_MAX or sfo_info.is_dir():
            raise FileError("Invalid archive!")
        entry_size = 0
        with zf.open(sfo_info, "r") as src, open(out, "wb") as dst:
            while True:
                chunk = src.read(ZIP_CHUNKSIZE)
                if not chunk:
                    break
                l = len(chunk)

                entry_size += l
                if entry_size > fs:
                    raise FileError("Invalid archive!")

                dst.write(chunk)
    return out

async def zip_unpack(src_file: str, dst_dir: str) -> int:
    try:
        return await asyncio.to_thread(_zip_unpack, src_file, dst_dir)
    except BadZipFile:
        raise FileError("Invalid archive!")
async def zip_unpack_sfo(src_file: str, dst_dir: str) -> str:
    try:
        return await asyncio.to_thread(_zip_unpack_sfo, src_file, dst_dir)
    except BadZipFile:
        raise FileError("Invalid archive!")

