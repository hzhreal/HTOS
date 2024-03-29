import aioftp
import os
import discord
import shutil
import aiofiles
from utils.orbis import check_titleid, resign, reregion_write, obtainCUSA, reregionCheck, OrbisError
from utils.constants import SYS_FILE_MAX, MGSV_TPP_TITLEID, MGSV_GZ_TITLEID

class FTPError(Exception):
    """Exception raised for errors relating to FTP."""
    def __init__(self, message: str) -> None:
        self.message = message

class FTPps:
    def __init__(self, IP: str, PORT: int, ENCRYPTED_LOCATION: str, DESTINATION_DIRECTORY: str, 
                 UPLOAD_DECRYPTED_REPLACE: str, UPLOAD_ENCRYPTED_PATH: str,
                 DOWNLOAD_ENCRYPTED_PATH: str, PARAM_PATH: str, KEYSTONEDIR: str, PNGPATH: str) -> None:
        
        self.IP = IP
        self.PORT = PORT
        self.ENCRYPTED_LOCATION = ENCRYPTED_LOCATION
        self.DESTINATION_DIRECTORY = DESTINATION_DIRECTORY
        self.UPLOAD_DECRYPTED_REPLACE = UPLOAD_DECRYPTED_REPLACE
        self.UPLOAD_ENCRYPTED_PATH = UPLOAD_ENCRYPTED_PATH
        self.DOWNLOAD_ENCRYPTED_PATH = DOWNLOAD_ENCRYPTED_PATH
        self.PARAM_PATH = PARAM_PATH
        self.KEYSTONEDIR = KEYSTONEDIR
        self.PNGPATH = PNGPATH
    
    CHUNKSIZE = 15 * 1024 * 1024 # 15MB
    PARAMSFO_NAME = "param.sfo"
    KEYSTONE_NAME = "keystone"

    
    @staticmethod
    async def checkSysFileSize(ftp: aioftp.Client.context, file: str, keystone: bool) -> bool:
        KEYSTONE_SIZE = 96
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
        
    async def downloadStream(self, ftp: aioftp.Client.context, file_to_download: str, recieve_path: str) -> None:
        # Download the file
        async with ftp.download_stream(file_to_download) as stream:
            async with aiofiles.open(recieve_path, "wb") as f:
                async for chunk in stream.iter_by_block(self.CHUNKSIZE):
                    await f.write(chunk)

    async def uploadStream(self, ftp: aioftp.Client.context, file_to_upload: str, recieve_path: str) -> None:
        async with aiofiles.open(file_to_upload, "rb") as f:
            stream = await ftp.upload_stream(recieve_path)
            while True:
                chunk = await f.read(self.CHUNKSIZE)
                if not chunk:
                    break
                await stream.write(chunk)
            await stream.finish()

    async def replacer(self, mount_location: str, replaceName: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(mount_location)
                local_file_path_replace = os.path.join(self.UPLOAD_DECRYPTED_REPLACE, replaceName)
                await self.uploadStream(ftp, local_file_path_replace, replaceName)
                
        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
    async def reregioner(self, mount_location: str, title_id: str, account_id: str) -> None:
        paramPath = os.path.join(self.PARAM_PATH, self.PARAMSFO_NAME)
        location_to_scesys = mount_location + "/sce_sys"
        decFilesPath = "" # used by MGSV re regioning to change crypt

        if not check_titleid(title_id):
            raise FTPError("Invalid title id!")
        
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                if not await FTPps.checkSysFileSize(ftp, self.PARAMSFO_NAME, keystone=False): 
                    raise FTPError("Invalid param.sfo size!")
                
                await self.downloadStream(ftp, self.PARAMSFO_NAME, paramPath)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
        if title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
            try:
                decFilesPath = self.DESTINATION_DIRECTORY
                await self.ftp_download_folder(mount_location, decFilesPath, ignoreSceSys=True)
            except FTPError as e:
                raise FTPError(e)

        await reregion_write(paramPath, title_id, decFilesPath)
        await resign(paramPath, account_id)

        if decFilesPath:
            try:
                await self.ftp_upload_folder(mount_location, decFilesPath)
            except FTPError as e:
                raise FTPError(e)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.uploadStream(ftp, paramPath, self.PARAMSFO_NAME)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
    async def retrievekeystone(self, location_to_scesys: str) -> None:
        full_keystone_path = os.path.join(self.KEYSTONEDIR, self.KEYSTONE_NAME)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
            
                if not await FTPps.checkSysFileSize(ftp, self.KEYSTONE_NAME, keystone=True):
                    raise FTPError("Invalid keystone size!")
                
                await self.downloadStream(ftp, self.KEYSTONE_NAME, full_keystone_path)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def keystoneswap(self, location_to_scesys: str) -> None:
        full_keystone_path = os.path.join(self.KEYSTONEDIR, self.KEYSTONE_NAME)
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.uploadStream(ftp, full_keystone_path, self.KEYSTONE_NAME)

        except aioftp.errors as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def uploadencrypted(self) -> None:
        encrypts = os.listdir(self.UPLOAD_ENCRYPTED_PATH)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(self.ENCRYPTED_LOCATION)

                for files in encrypts:
                    encrypted_local = os.path.join(self.UPLOAD_ENCRYPTED_PATH, files)
                    await self.uploadStream(ftp, encrypted_local, files)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def dlparam(self, location_to_scesys: str, account_id: str) -> None:
        fullparam_dl = os.path.join(self.PARAM_PATH, self.PARAMSFO_NAME)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                if not await FTPps.checkSysFileSize(ftp, self.PARAMSFO_NAME, keystone=False):
                    raise FTPError("Invalid param.sfo size!")
                
                await self.downloadStream(ftp, self.PARAMSFO_NAME, fullparam_dl)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

        await resign(fullparam_dl, account_id)
        
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.uploadStream(ftp, fullparam_dl, self.PARAMSFO_NAME)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def deleteuploads(self, savenames: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(self.ENCRYPTED_LOCATION)
                await ftp.remove(savenames)

                savenames_bin = savenames + ".bin"

                await ftp.remove(savenames_bin)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def dlparamonly_grab(self, location_to_scesys: str) -> None:
        param_local = self.PARAM_PATH
        fullparam_dl = os.path.join(param_local, self.PARAMSFO_NAME)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                if not await FTPps.checkSysFileSize(ftp, self.PARAMSFO_NAME, keystone=False):
                    raise FTPError("Invalid param.sfo size!")

                fullparam_dl = os.path.join(param_local, self.PARAMSFO_NAME)
                await self.downloadStream(ftp, self.PARAMSFO_NAME, fullparam_dl)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def delete_folder_contents_ftp(self, folder_path: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.remove(folder_path)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
    async def makemount(self, folder1: str, folder2: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.make_directory(folder1)
                await ftp.make_directory(folder2)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def make1(self, path: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.make_directory(path)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def swappng(self, location_to_scesys: str) -> None:
        pngname = "icon0.png"
        full_pngpath = os.path.join(self.PNGPATH, pngname)
        
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.uploadStream(ftp, full_pngpath, pngname)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
    
    async def ftp_download_folder(self, folder_path: str, downloadpath: str, ignoreSceSys: bool) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.download(folder_path, downloadpath, write_into=True)

            if ignoreSceSys: 
                shutil.rmtree(os.path.join(downloadpath, "sce_sys"))

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
    async def ftp_upload_folder(self, folderpath: str, local_path: str) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(folderpath)
                await ftp.upload(local_path, write_into=True)
        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
            
    async def dlencrypted_bulk(self, reregion: bool, account_id: str, savenames: str) -> None:
    
        try: title_id = await obtainCUSA(self.PARAM_PATH)
        except OrbisError as e: raise OrbisError(e)

        savefilespath = os.path.join(self.DOWNLOAD_ENCRYPTED_PATH, "PS4", "SAVEDATA", account_id, title_id)

        if not os.path.exists(savefilespath):
            os.makedirs(savefilespath)

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(self.ENCRYPTED_LOCATION)
                newsavenames = savenames.rsplit("_", 1)[0]
                fulldl_process = os.path.join(savefilespath, newsavenames)
                await self.downloadStream(ftp, savenames, fulldl_process)

                savenames_bin = savenames + ".bin"
                newsavenames_bin = newsavenames + ".bin"
                fulldl_process1 = os.path.join(savefilespath, newsavenames_bin)
                await self.downloadStream(ftp, savenames_bin, fulldl_process1)
            
            if reregion: 
                reregionCheck(title_id, savefilespath, fulldl_process, fulldl_process1)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")   
            
    async def uploadencrypted_bulk(self, savename: str) -> None:
        savefiles = [os.path.join(self.UPLOAD_ENCRYPTED_PATH, savename), os.path.join(self.UPLOAD_ENCRYPTED_PATH, savename + ".bin")]

        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(self.ENCRYPTED_LOCATION)
                    
                for file in savefiles:
                    basename = os.path.basename(file)
                    await self.uploadStream(ftp, file, basename)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

    async def upload_scesysContents(self, ctx: discord.ApplicationContext, filepaths: list[str], sce_sysPath: str) -> None:
        
        for filepath in filepaths:
            fullPath = os.path.join(self.UPLOAD_DECRYPTED_REPLACE, filepath)
            embSuccess = discord.Embed(title="Upload alert: Successful", description=f"File '{filepath}' has been successfully uploaded and saved.",colour=0x854bf7)        
            embSuccess.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")     
            embSuccess.set_footer(text="Made with expertise by HTOP")

            try:
                async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                    await ftp.change_directory(sce_sysPath)
                    await self.uploadStream(ftp, fullPath, filepath)

                    await ctx.edit(embed=embSuccess)
            except aioftp.errors.AIOFTPException as e:
                print(f"[FTP ERROR]: {e}")
                raise FTPError("An unexpected error!")
    
    async def ftpListContents(self, mountpath: str) -> list[str]:
        files = []
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(mountpath)
                async for path in ftp.list(recursive=True):
                    files.append(path)
        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")

        # exclude sce_sys, parent- and working directory)
        files = [
            str(file) 
            for file, attributes in files 
            if "sce_sys" not in file.parts 
            and file.name not in ".." and file.name not in "."
            and attributes.get("type", "") != "dir"
            and attributes.get("type", "") != "cdir"
            and attributes.get("type", "") != "pdir"
            ]

        return files
    
    async def deleteList(self, uploadDir: str, fileList: list[str]) -> None:
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(uploadDir)
                for fileName in fileList:
                    if (await ftp.exists(fileName)):
                        await ftp.remove(fileName)

        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
        
    async def testConnection(self) -> None:
        async with aioftp.Client.context(self.IP, self.PORT):
           pass

    async def upload_sfo(self, paramPath: str, location_to_scesys: str) -> None:
        paramPath = os.path.join(paramPath, self.PARAMSFO_NAME)
        try:
            async with aioftp.Client.context(self.IP, self.PORT) as ftp:
                await ftp.change_directory(location_to_scesys)
                await self.uploadStream(ftp, paramPath, self.PARAMSFO_NAME)
        except aioftp.errors.AIOFTPException as e:
            print(f"[FTP ERROR]: {e}")
            raise FTPError("An unexpected error!")
