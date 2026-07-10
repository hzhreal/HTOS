import asyncio
import os
from zipfile import ZipFile
from zipfile import (
    #ZIP_BZIP2,
    #ZIP_DEFLATED,
    #ZIP_LZMA,
    ZIP_STORED
)

ZIP_COMPRESSION_MODE = ZIP_STORED
ZIP_COMPRESSION_LEVEL = None
def _zip_pack(src_dir: str, dst_name: str) -> None:
    dst = os.path.join(src_dir, dst_name)
    with ZipFile(dst, "w", compression=ZIP_COMPRESSION_MODE, compresslevel=ZIP_COMPRESSION_LEVEL) as f:
        # crawling through directory and subdirectories
        for dirpath, _, filenames in os.walk(src_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.abspath(filepath) == os.path.abspath(dst):
                    continue
                archive_path = os.path.relpath(filepath, src_dir)
                # writing each file one by one without the top-level folder
                f.write(filepath, archive_path)

async def zip_pack(src_dir: str, dst_name: str) -> None:
    await asyncio.to_thread(_zip_pack, src_dir, dst_name)

