import aioftp
import os
import discord
import shutil
import aiofiles
import aiofiles.os
import asyncio
from aioftp.errors import AIOFTPException

from network.exceptions import FTPError
from utils.constants import GENERAL_CHUNKSIZE, SYS_FILE_MAX, KEYSTONE_SIZE, KEYSTONE_NAME, PARAM_NAME, ICON0_NAME, SCE_SYS_NAME, logger
from utils.embeds import embuplSuccess

FTP_SEMAPHORE_ALT = asyncio.Semaphore(16)

class FTPps:
    """Async functions to interact with the FTP server."""
    def __init__(self, ip: str, port: int, savepair_remote_path: str, download_decrypted_path: str, 
                 upload_decrypted_path: str, upload_encrypted_path: str,
                 download_encrypted_path: str, sfo_path: str, keystone_path: str, png_path: str) -> None:

        self.ip = ip
        self.port = port
        # paths to directories
        self.savepair_remote_path = savepair_remote_path
        self.download_decrypted_path = download_decrypted_path
        self.upload_decrypted_path = upload_decrypted_path
        self.upload_encrypted_path = upload_encrypted_path
        self.download_encrypted_path = download_encrypted_path
        self.sfo_path = sfo_path
        self.keystone_path = keystone_path
        self.png_path = png_path

        # paths to file
        self.sfo_file_path = os.path.join(self.sfo_path, PARAM_NAME)
        self.keystone_file_path = os.path.join(self.keystone_path, KEYSTONE_NAME)
        self.png_file_path = os.path.join(self.png_path, ICON0_NAME)

    CHUNKSIZE = GENERAL_CHUNKSIZE
    CONNECTION_TIMEOUT = 10 # seconds

    @staticmethod
    async def check_sys_filesize(ftp: aioftp.Client, file: str, keystone: bool) -> bool:
        file_data = await ftp.stat(file)

        file_type = file_data["type"]
        if file_type != "file":
            return False

        size_unsure = file_data["size"]

        if size_unsure is None:
            return False

        size = int(size_unsure)

        if keystone and size != KEYSTONE_SIZE:
            return False
        elif size > SYS_FILE_MAX or size == 0:
            return False
        return True

    @staticmethod
    async def free_ctx(ftp: aioftp.Client) -> None:
        await ftp.quit()
        ftp.close()

    async def download_stream(self, ftp: aioftp.Client, file_to_download: str, recieve_path: str) -> None:
        # Download the file
        async with ftp.download_stream(file_to_download) as stream:
            async with aiofiles.open(recieve_path, "wb") as f:
                async for chunk in stream.iter_by_block(self.CHUNKSIZE):
                    await f.write(chunk)
        logger.info(f"Downloaded {file_to_download} to {recieve_path}")

    async def upload_stream(self, ftp: aioftp.Client, file_to_upload: str, recieve_path: str) -> None:
        # Upload the file
        async with aiofiles.open(file_to_upload, "rb") as f:
            stream = await ftp.upload_stream(recieve_path)
            while True:
                chunk = await f.read(self.CHUNKSIZE)
                if not chunk:
                    break
                await stream.write(chunk)
            await stream.finish()
        logger.info(f"Uploaded {file_to_upload} to {recieve_path}")

    async def replacer(self, mount_location: str, replaceName: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(mount_location)
                local_file_path_replace = os.path.join(self.upload_decrypted_path, replaceName)
                await self.upload_stream(ftp, local_file_path_replace, replaceName)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def retrieve_keystone(self, location_to_scesys: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(location_to_scesys)

                if not await FTPps.check_sys_filesize(ftp, KEYSTONE_NAME, keystone=True):
                    raise FTPError("Invalid keystone size!")

                await self.download_stream(ftp, KEYSTONE_NAME, self.keystone_file_path)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def upload_keystone(self, location_to_scesys: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.upload_stream(ftp, self.keystone_file_path, KEYSTONE_NAME)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def download_sfo(self, location_to_scesys: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(location_to_scesys)
                if not await FTPps.check_sys_filesize(ftp, PARAM_NAME, keystone=False):
                    raise FTPError("Invalid param.sfo size!")

                await self.download_stream(ftp, PARAM_NAME, self.sfo_file_path)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def upload_sfo(self, location_to_scesys: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.upload_stream(ftp, self.sfo_file_path, PARAM_NAME)
        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def delete_folder_contents(self, folder_path: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                if await ftp.exists(folder_path):
                    await ftp.remove(folder_path)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def make1(self, path: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                if await ftp.exists(path):
                    await ftp.remove(path)
                await ftp.make_directory(path)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def swap_png(self, location_to_scesys: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.upload_stream(ftp, self.png_file_path, ICON0_NAME)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def download_folder(self, folder_path: str, downloadpath: str, ignoreSceSys: bool) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.download(folder_path, downloadpath, write_into=True)

            logger.info(f"Downloaded {folder_path} to {downloadpath}")
        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

        logger.info(f"Downloaded {folder_path} to {downloadpath}")

        if ignoreSceSys:
            shutil.rmtree(os.path.join(downloadpath, SCE_SYS_NAME))

    async def upload_folder(self, folderpath: str, local_path: str) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(folderpath)
                await ftp.upload(local_path, write_into=True)

            logger.info(f"Uploaded {local_path} to {folderpath}")

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def dlencrypted_bulk(self, account_id: str, savename: str, title_id: str, reregion: bool = False) -> None:
        savefilespath = os.path.join(self.download_encrypted_path, "PS4", "SAVEDATA", account_id, title_id)
        await aiofiles.os.makedirs(savefilespath, exist_ok=True)

        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(self.savepair_remote_path)
                new_savename = savename.rsplit("_", 1)[0]
                new_savepath = os.path.join(savefilespath, new_savename)
                await self.download_stream(ftp, savename, new_savepath)

                savename_bin = savename + ".bin"
                new_savenames_bin = new_savename + ".bin"
                new_savepath_bin = os.path.join(savefilespath, new_savenames_bin)
                await self.download_stream(ftp, savename_bin, new_savepath_bin)

            if reregion:
                from utils.orbis import reregion_check
                await reregion_check(title_id, new_savepath)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def uploadencrypted_bulk(self, savename: str) -> None:
        savefiles = [os.path.join(self.upload_encrypted_path, savename), os.path.join(self.upload_encrypted_path, savename + ".bin")]

        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(self.savepair_remote_path)

                for file in savefiles:
                    basename = os.path.basename(file)
                    await self.upload_stream(ftp, file, basename)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def upload_scesysContents(self, ctx: discord.ApplicationContext | discord.Message, filepaths: list[str], sce_sysPath: str) -> None:
        n = len(filepaths)
        i = 1
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(sce_sysPath)
                for filepath in filepaths:
                    filename = os.path.basename(filepath)
                    emb = embuplSuccess.copy()
                    emb.description = emb.description.format(filename=filename, i=i, filecount=n)

                    await self.upload_stream(ftp, filepath, filename)
                    await ctx.edit(embed=emb)
                    i += 1

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def list_files(self, target_path: str, recursive: bool = True) -> list[str]:
        files = []
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                if await ftp.exists(target_path):
                    await ftp.change_directory(target_path)
                    async for path in ftp.list(recursive=recursive):
                        files.append(path)
        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

        # exclude sce_sys, parent- and working directory)
        files = [
            str(file)
            for file, attributes in files
            if SCE_SYS_NAME not in file.parts
            and file.name not in ".." and file.name not in "."
            and attributes.get("type", "") != "dir"
            and attributes.get("type", "") != "cdir"
            and attributes.get("type", "") != "pdir"
        ]
        return files

    async def delete_list(self, upload_dir: str, file_list: list[str]) -> None:
        try:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT) as ftp:
                await ftp.change_directory(upload_dir)
                for filename in file_list:
                    if await ftp.exists(filename):
                        await ftp.remove(filename)

        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

    async def test_connection(self) -> None:
        async with FTP_SEMAPHORE_ALT:
            async with aioftp.Client.context(self.ip, self.port, connection_timeout=self.CONNECTION_TIMEOUT):
                pass

    async def create_ctx(self) -> aioftp.Client:
        try:
            ctx = aioftp.Client(connection_timeout=self.CONNECTION_TIMEOUT)
            await ctx.connect(self.ip, self.port)
        except AIOFTPException as e:
            logger.exception(f"[FTP ERROR]: {e}")
            raise FTPError("FTP ERROR: CONNECTION FAIL!")
        except TimeoutError:
            logger.error("Failed to connect to FTP!")
            raise FTPError("FTP ERROR!")

        return ctx
