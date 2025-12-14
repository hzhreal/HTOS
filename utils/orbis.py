import re
import aiofiles
import aiofiles.os
import os
import discord
import asyncio
import struct
import shutil
from enum import Enum
from dataclasses import dataclass

from network.ftp_functions import FTPps
from network.socket_functions import SocketPS
from utils.constants import (
    MOUNT_LOCATION, XENO2_TITLEID, MGSV_TPP_TITLEID, MGSV_GZ_TITLEID, FILE_LIMIT_DISCORD, SCE_SYS_CONTENTS, SYS_FILE_MAX, 
    SEALED_KEY_ENC_SIZE, MAX_FILENAME_LEN, PS_UPLOADDIR, MAX_PATH_LEN, RANDOMSTRING_LENGTH, MANDATORY_SCE_SYS_CONTENTS, SCE_SYS_NAME
)
from utils.embeds import embfn, embFileLarge, embnvSys, embpn, embnvBin
from utils.extras import generate_random_string, obtain_savenames, completed_print
from utils.type_helpers import uint32, uint64, utf_8, utf_8_s, TypeCategory
from utils.workspace import enumerate_files
from utils.exceptions import OrbisError
from utils.conversions import bytes_to_mb

SFO_MAGIC = 0x46535000
SFO_VERSION = 0x0101

SAVEDIR_RE = re.compile(r"^[a-zA-Z0-9\-_.\@]+$")
TITLE_ID_RE = re.compile(r"^CUSA\d{5}$")
ACCID_RE = re.compile(r"^[0-9a-fA-F]+$")

# account_id: uint64
# attribute: uint32
# category: utf-8
# detail: utf-8
# format: utf-8
# maintitle: utf-8
# params: utf-8-s
# savedata_blocks: uint64
# savedata_directory: utf-8
# savedata_list_param: uint32
# subtitle: utf-8
# title_id: utf-8

SFO_TYPES = {
    "ACCOUNT_ID":           uint64(0, "little"),
    "ATTRIBUTE":            uint32(0, "little"),
    "CATEGORY":             utf_8(""),
    "DETAIL":               utf_8(""),
    "FORMAT":               utf_8(""),
    "MAINTITLE":            utf_8(""),
    "PARAMS":               utf_8_s(""),
    "SAVEDATA_BLOCKS":      uint64(0, "little"),
    "SAVEDATA_DIRECTORY":   utf_8(""),
    "SAVEDATA_LIST_PARAM":  uint32(0, "little"),
    "SUBTITLE":             utf_8(""),
    "TITLE_ID":             utf_8("")
}

@dataclass
class SaveBatch:
    fInstance: FTPps
    sInstance: SocketPS
    user_id: str
    entry: list[str]
    mount_paths: list[str]
    new_download_encrypted_path: str

    async def construct(self) -> None:
        dname = os.path.dirname(self.entry[0])
        self.rand_str = os.path.basename(dname)
        self.fInstance.upload_encrypted_path = dname
        self.fInstance.download_encrypted_path = os.path.join(self.new_download_encrypted_path, self.rand_str)

        if not await aiofiles.os.path.exists(self.fInstance.download_encrypted_path) and self.new_download_encrypted_path:
            await aiofiles.os.mkdir(self.fInstance.download_encrypted_path)

        self.mount_location = MOUNT_LOCATION + "/" + self.rand_str
        self.mount_paths.append(self.mount_location)
        self.location_to_scesys = self.mount_location + f"/{SCE_SYS_NAME}"

        self.savenames = await obtain_savenames(self.entry)
        self.savecount = len(self.savenames)

        self.entry = enumerate_files(self.entry, self.rand_str)

        self.printed = completed_print(self.savenames)

@dataclass
class SaveFile:
    class ElementChoice(Enum):
        SFO = 0
        KEYSTONE = 1

    path: str
    batch: SaveBatch
    reregion_check: bool = False
    validity_check: bool = True

    async def construct(self) -> None:
        self.basename = os.path.basename(self.path)
        self.dirname = os.path.dirname(self.path)
        self.realSave = f"{self.basename}_{self.batch.rand_str}"
        self.title_id = None
        self.sfo_ctx = None
        self.downloaded_sys_elements = set()

        await aiofiles.os.rename(self.path, os.path.join(self.dirname, self.realSave))
        await aiofiles.os.rename(self.path + ".bin", os.path.join(self.dirname, self.realSave + ".bin"))

    async def dump(self) -> None:
        await self.batch.fInstance.uploadencrypted_bulk(self.realSave)
        await self.batch.fInstance.make1(self.batch.mount_location)
        await self.batch.sInstance.socket_dump(self.batch.mount_location, self.realSave)
        if self.validity_check:
            sys_files = await self.batch.fInstance.list_files(self.batch.location_to_scesys, recursive=False)
            sys_files_validator(sys_files)

    async def resign(self) -> None:
        if not self.ElementChoice.SFO in self.downloaded_sys_elements:
            await self.batch.fInstance.download_sfo(self.batch.location_to_scesys)
        if self.sfo_ctx is None:
            self.sfo_ctx = await sfo_ctx_create(self.batch.fInstance.sfo_file_path)
        if self.title_id is None:
            self.title_id = obtainCUSA(self.sfo_ctx)
        resign(self.sfo_ctx, self.batch.user_id)
        if self.reregion_check:
            if self.ElementChoice.KEYSTONE in self.downloaded_sys_elements:
                await self.batch.fInstance.upload_keystone(self.batch.location_to_scesys)
            await self.__reregion()
        await sfo_ctx_write(self.sfo_ctx, self.batch.fInstance.sfo_file_path)
        await self.batch.fInstance.upload_sfo(self.batch.location_to_scesys)
        await self.batch.sInstance.socket_update(self.batch.mount_location, self.realSave)
        await self.batch.fInstance.dlencrypted_bulk(self.batch.user_id, self.realSave, self.title_id, self.reregion_check)

    async def download_sys_elements(self, elements: list[ElementChoice]) -> None:
        for element in elements:
            match element:
                case self.ElementChoice.SFO:
                    await self.batch.fInstance.download_sfo(self.batch.location_to_scesys)
                    self.sfo_ctx = await sfo_ctx_create(self.batch.fInstance.sfo_file_path)
                    self.title_id = obtainCUSA(self.sfo_ctx)
                    self.downloaded_sys_elements.add(self.ElementChoice.SFO)
                case self.ElementChoice.KEYSTONE:
                    await self.batch.fInstance.retrieve_keystone(self.batch.location_to_scesys)
                    self.downloaded_sys_elements.add(self.ElementChoice.KEYSTONE)

    async def __reregion(self) -> None:
        dec_path = ""
        if self.title_id in MGSV_TPP_TITLEID or self.title_id in MGSV_GZ_TITLEID:
            dec_path = self.batch.fInstance.download_decrypted_path
            await self.batch.fInstance.download_folder(self.batch.mount_location, dec_path, True)
        await reregion_write(self.sfo_ctx, self.title_id, dec_path)
        if dec_path:
            await self.batch.fInstance.upload_folder(self.batch.mount_location, dec_path)
            shutil.rmtree(dec_path)
            await aiofiles.os.mkdir(dec_path)

@dataclass
class PFSHeader:
    basic_block_size: int
    data_block_count: int
    size: int

@dataclass
class SFOHeader:
    magic: int
    version: int
    key_table_offset: int
    data_table_offset: int
    num_entries: int

@dataclass
class SFOIndexTable:
    key_offset: int
    param_format: int
    param_length: int
    param_max_length: int
    data_offset: int

@dataclass
class SFOContextParam:
    key: str
    format: int
    length: int
    max_length: int
    actual_length: int
    value: bytearray

    def as_dict(self) -> dict[str, str | int | bytearray]:
        info = vars(self)
        value = 0

        match self.key:
            case "ACCOUNT_ID":
                try: 
                    accid = utf_8(self.value)
                    value = accid.value
                except UnicodeDecodeError:
                    accid = uint64(self.value, "little")
                    value = hex(accid.value)
            case "SAVEDATA_BLOCKS":
                blocks = uint64(self.value, "little")
                value = hex(blocks.value)
            case "CATEGORY" | "DETAIL" | "FORMAT" | "MAINTITLE" | "SAVEDATA_DIRECTORY" | "SUBTITLE" | "TITLE_ID":
                ctx = utf_8(self.value)
                value = ctx.value
            case "ATTRIBUTE" | "SAVEDATA_LIST_PARAM":
                ctx = uint32(self.value, "little")
                value = hex(ctx.value)
            case "PARAMS":
                params = utf_8_s(self.value)
                value = params.value

        info["converted_value"] = value
        return info

class SFOContext:
    """Instance creator for param.sfo r/w."""
    def __init__(self) -> None:
        self.params = []

    def sfo_read(self, sfo: bytearray) -> None:
        if len(sfo) < 20:
            raise OrbisError("Invalid param.sfo size!")

        header_data = struct.unpack("<IIIII", sfo[:20])
        header = SFOHeader(*header_data)

        if header.magic != SFO_MAGIC:
            raise OrbisError("Invalid param.sfo header magic!")

        try:
            for i in range(header.num_entries):
                index_offset = 20 + i * 16
                index_data = struct.unpack("<HHIII", sfo[index_offset:index_offset + 16])
                index_table = SFOIndexTable(*index_data)

                param_offset = header.key_table_offset + index_table.key_offset
                param_key = sfo[param_offset:sfo.find(b"\x00", param_offset)].decode("utf-8")

                param_data_offset = header.data_table_offset + index_table.data_offset
                param_data = sfo[param_data_offset:param_data_offset + index_table.param_max_length]

                param = SFOContextParam(key=param_key, format=index_table.param_format,
                                        length=index_table.param_length, max_length=index_table.param_max_length,
                                        value=param_data, actual_length=index_table.param_max_length)

                self.params.append(param)
        except (struct.error, UnicodeDecodeError, IndexError):
            raise OrbisError("Param.sfo could not be parsed!")

    def sfo_write(self) -> bytearray:
        num_params = len(self.params)
        key_table_size, data_table_size = 0, 0

        for param in self.params:
            key_table_size += len(param.key) + 1
            data_table_size += param.actual_length

        sfo_size = 20 + num_params * 16 + key_table_size + data_table_size
        key_table_size += (sfo_size + 7) & ~7 - sfo_size
        sfo_size = (sfo_size + 7) & ~7

        sfo = bytearray(b"\0" * sfo_size)

        header = SFOHeader(SFO_MAGIC, SFO_VERSION, 20 + num_params * 16, (20 + num_params * 16 + key_table_size) + 2, num_params)

        try:
            struct.pack_into("<IIIII", sfo, 0, header.magic, header.version, header.key_table_offset, header.data_table_offset, header.num_entries)
        except struct.error:
            raise OrbisError("Failed to generate a param.sfo!")

        key_offset, data_offset = 0, 0
        for i, param in enumerate(self.params):
            index_offset = 20 + i * 16
            index_table = SFOIndexTable(key_offset, param.format, param.length, param.max_length, data_offset)

            try: 
                struct.pack_into("<HHIII", sfo, index_offset, index_table.key_offset, index_table.param_format, index_table.param_length, index_table.param_max_length, index_table.data_offset)
            except struct.error:
                raise OrbisError("Failed to generate a param.sfo!")

            key_offset += len(param.key) + 1
            data_offset += param.actual_length

        for i, param in enumerate(self.params):
            index_table = SFOIndexTable(*struct.unpack("<HHIII", sfo[20 + i * 16: 20 + i * 16 + 16]))
            key_offset = index_table.key_offset
            data_offset = index_table.data_offset

            try:
                struct.pack_into(f"{len(param.key)+1}s", sfo, header.key_table_offset + key_offset, param.key.encode("utf-8"))
                struct.pack_into(f"{param.actual_length}s", sfo, header.data_table_offset + data_offset, param.value)
            except struct.error:
                raise OrbisError("Failed to generate a param.sfo!")

        return sfo

    def sfo_patch_parameter(self, parameter: str, new_data: str | int) -> None:
        param: SFOContextParam = next((param for param in self.params if param.key == parameter), None)
        if not param:
            raise OrbisError(f"Invalid parameter: {parameter}!")

        param_type: uint32 | uint64 | utf_8 | utf_8_s = SFO_TYPES.get(parameter)
        if not param_type:
            raise OrbisError(f"Unsupported parameter: {parameter}!")

        match param_type:
            case uint32():
                ctx = uint32(new_data, "little")
            case uint64():
                ctx = uint64(new_data, "little")
            case utf_8():
                ctx = utf_8(new_data)
            case utf_8_s():
                ctx = utf_8_s(new_data)

        max_len = param.max_length | param.actual_length

        if ctx.CATEGORY == TypeCategory.CHARACTER:
            if ctx.bytelen >= max_len:
               raise OrbisError(f"The parameter: {parameter} reached the max length it has of {max_len}! Remember last byte is reserved for null termination for this parameter.")
        else:
            if ctx.bytelen > max_len:
                raise OrbisError(f"The parameter: {parameter} reached the max length it has of {max_len}!")

        param.length = ctx.bytelen
        param.value = ctx.as_bytes

    def sfo_get_param_value(self, parameter: str) -> bytes:
        param: SFOContextParam = next((param for param in self.params if param.key == parameter), None)
        if param:
            return param.value
        else:
            raise OrbisError(f"Invalid parameter: {parameter}!")

    def sfo_get_param_data(self) -> list[dict[str, str | int | bytearray]]:
        param_data = []
        for param in self.params:
            param: SFOContextParam
            try:
                param_data.append(param.as_dict())
            except (struct.error, UnicodeDecodeError):
                raise OrbisError("Failed to get param data!")
        return param_data

class PfsSKKey:
    def __init__(self, data: bytearray) -> None:
        assert len(data) == self.SIZE

        self.MAGIC   = data[:0x08]
        self.VERSION = data[0x08:0x10]
        self.IV      = data[0x10:0x20]
        self.KEY     = data[0x20:0x40]
        self.SHA256  = data[0x40:0x60]

        self.data    = data
        self.dec_key = bytearray()

    SIZE = 0x60
    MAGIC_VALUE = b"pfsSKKey"

    def validate(self) -> bool:
        if self.MAGIC != self.MAGIC_VALUE:
            return False
        return True

    def as_array(self) -> list[int]:
        return list(self.data)

def keyset_to_fw(keyset: int) -> str:
    match keyset:
        case 1:
            return "Any"
        case 2:
            return "4.50+"
        case 3:
            return "4.70+"
        case 4:
            return "5.00+"
        case 5:
            return "5.50+"
        case 6:
            return "6.00+"
        case 7:
            return "6.50+"
        case 8:
            return "7.00+"
        case 9:
            return "7.50+"
        case 10:
            return "8.00+"
        case _:
            return "?"

def checkid(accid: str) -> bool:
    if len(accid) != 16 or not bool(ACCID_RE.fullmatch(accid)):
        return False
    else:
        return True

def handle_accid(user_id: str) -> str:
    user_id = hex(int(user_id)) # convert decimal to hex
    user_id = user_id[2:] # remove 0x
    user_id = user_id.zfill(16) # pad to 16 length with zeros

    return user_id

async def check_saves(
          ctx: discord.ApplicationContext | discord.Message, 
          attachments: list[discord.message.Attachment], 
          ps_save_pair_upload: bool, 
          sys_files: bool, 
          ignore_filename_check: bool, 
          savesize: int | None = None
        ) -> list[discord.message.Attachment]:

    """Handles file checks universally through discord upload."""
    valid_files = []
    total_count = 0
    if ps_save_pair_upload:
        valid_files = await save_pair_check(ctx, attachments)
        return valid_files

    for attachment in attachments:
        if len(attachment.filename) > MAX_FILENAME_LEN and not ignore_filename_check:
            emb = embfn.copy()
            emb.description = emb.description.format(filename=attachment.filename, len=len(attachment.filename), max=MAX_FILENAME_LEN)
            await ctx.edit(embed=emb)
            await asyncio.sleep(1)

        elif attachment.size > FILE_LIMIT_DISCORD:
            emb = embFileLarge.copy()
            emb.description = emb.description.format(filename=attachment.filename, max=bytes_to_mb(FILE_LIMIT_DISCORD))
            await ctx.edit(embed=emb)
            await asyncio.sleep(1)

        elif sys_files and (attachment.filename not in SCE_SYS_CONTENTS or attachment.size > SYS_FILE_MAX):
            emb = embnvSys.copy()
            emb.description = emb.description.format(filename=attachment.filename)
            await ctx.edit(embed=emb)
            await asyncio.sleep(1)

        elif savesize is not None and total_count > savesize:
            raise OrbisError(f"The files you are uploading for this save exceeds the savesize {bytes_to_mb(savesize)} MB!")

        else: 
            total_count += attachment.size
            valid_files.append(attachment)

    return valid_files

async def save_pair_check(ctx: discord.ApplicationContext | discord.Message, attachments: list[discord.message.Attachment]) -> list[discord.message.Attachment]:
    """Makes sure the save pair through discord upload is valid."""
    valid_attachments_check1 = []
    for attachment in attachments:
        filename = attachment.filename + f"_{'X' * RANDOMSTRING_LENGTH}"
        filename_len = len(filename)
        path_len = len(PS_UPLOADDIR + "/" + filename + "/")

        if filename_len > MAX_FILENAME_LEN:
            emb = embfn.copy()
            emb.description = emb.description.format(filename=attachment.filename, len=filename_len, max=MAX_FILENAME_LEN)
            await ctx.edit(embed=emb)
            await asyncio.sleep(1)

        elif path_len > MAX_PATH_LEN:
            emb = embpn.copy()
            emb.description = emb.description.format(filename=attachment.filename, len=path_len, max=MAX_PATH_LEN)
            await ctx.edit(embed=emb)
            await asyncio.sleep(1)

        elif attachment.filename.endswith(".bin"):
            if attachment.size != SEALED_KEY_ENC_SIZE:
                emb = embnvBin.copy()
                emb.description = emb.description.format(filename=attachment.filename, size=SEALED_KEY_ENC_SIZE)
                await ctx.edit(embed=emb)
                await asyncio.sleep(1)
            else:
                valid_attachments_check1.append(attachment)
        else:
            if attachment.size > FILE_LIMIT_DISCORD:
                emb = embFileLarge.copy()
                emb.description = emb.description.format(filename=attachment.filename, max=bytes_to_mb(FILE_LIMIT_DISCORD))
                await ctx.edit(embed=emb)
                await asyncio.sleep(1)
            else:
                valid_attachments_check1.append(attachment)

    valid_attachments_final = []
    for attachment in valid_attachments_check1:
        if attachment.filename.endswith(".bin"): # look for corresponding file
            for attachment_nested in valid_attachments_check1:
                filename_nested = attachment_nested.filename
                if filename_nested == attachment.filename: continue

                elif filename_nested == os.path.splitext(attachment.filename)[0]:
                    valid_attachments_final.append(attachment)
                    valid_attachments_final.append(attachment_nested)
                    break

    return valid_attachments_final

async def sfo_ctx_create(sfo_path: str) -> SFOContext:
    async with aiofiles.open(sfo_path, "rb") as sfo:
        sfo_data = bytearray(await sfo.read())
    ctx = SFOContext()
    ctx.sfo_read(sfo_data)
    return ctx

async def sfo_ctx_write(ctx: SFOContext, sfo_path: str) -> None:
    sfo_data = ctx.sfo_write()
    async with aiofiles.open(sfo_path, "wb") as sfo:
        await sfo.write(sfo_data)

def sfo_ctx_patch_parameters(ctx: SFOContext, **patches: int | str) -> None:
    # ignore parameters with no value
    filtered_patches = {key: value for key, value in patches.items() if value}

    for key in filtered_patches:
        ctx.sfo_patch_parameter(key, filtered_patches[key])

def obtainCUSA(ctx: SFOContext) -> str:
    """Obtains TITLE_ID from sfo file."""
    data_title_id = ctx.sfo_get_param_value("TITLE_ID")
    data_title_id = bytearray(filter(lambda x: x != 0x00, data_title_id))

    try: 
        title_id = data_title_id.decode("utf-8")
    except UnicodeDecodeError: 
        raise OrbisError("Invalid title ID in param.sfo!")

    if not check_titleid(title_id):
        raise OrbisError("Invalid title id!")

    return title_id

def check_titleid(titleid: str) -> bool:
    return bool(TITLE_ID_RE.fullmatch(titleid))

def resign(ctx: SFOContext, account_id: str) -> None:
    """Traditional resigning."""
    ctx.sfo_patch_parameter("ACCOUNT_ID", account_id)

async def reregion_write(ctx: SFOContext, title_id: str, dec_files_folder: str) -> None:
    """Writes the new title id in the sfo file, changes the SAVEDATA_DIRECTORY for the games needed."""
    from utils.namespaces import Crypto

    ctx.sfo_patch_parameter("TITLE_ID", title_id)

    if title_id in XENO2_TITLEID:
        newname = title_id + "01"
        ctx.sfo_patch_parameter("SAVEDATA_DIRECTORY", newname)

    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
        try: 
            await Crypto.MGSV.reregion_change_crypt(dec_files_folder, title_id)
        except (ValueError, IOError, IndexError):
            raise OrbisError("Error changing MGSV crypt!")

        newname = Crypto.MGSV.KEYS[title_id]["name"]
        ctx.sfo_patch_parameter("SAVEDATA_DIRECTORY", newname)

async def reregion_check(title_id: str, savePath: str, original_savePath: str, original_savePath_bin: str) -> None:
    """Renames the save after Re-regioning for the games that need it, random string is appended at the end for no overwriting."""
    from utils.namespaces import Crypto

    if title_id in XENO2_TITLEID:
        newnameFile = os.path.join(savePath, title_id + "01")
        newnameBin = os.path.join(savePath, title_id + "01.bin")
        if await aiofiles.os.path.exists(newnameFile) and await aiofiles.os.path.exists(newnameBin):
            randomString = generate_random_string(RANDOMSTRING_LENGTH)
            newnameFile = os.path.join(savePath, title_id + f"01_{randomString}")
            newnameBin = os.path.join(savePath, title_id + f"01_{randomString}.bin")
        if await aiofiles.os.path.exists(original_savePath) and await aiofiles.os.path.exists(original_savePath_bin):
            await aiofiles.os.rename(original_savePath, newnameFile)
            await aiofiles.os.rename(original_savePath_bin, newnameBin)

    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_TPP_TITLEID:
        new_regionName = Crypto.MGSV.KEYS[title_id]["name"]
        newnameFile = os.path.join(savePath, new_regionName)
        newnameBin = os.path.join(savePath, new_regionName + ".bin")
        if await aiofiles.os.path.exists(newnameFile) and await aiofiles.os.path.exists(newnameBin):
            randomString = generate_random_string(RANDOMSTRING_LENGTH)
            newnameFile = os.path.join(savePath, new_regionName + f"_{randomString}")
            newnameBin = os.path.join(savePath, new_regionName + f"_{randomString}.bin")
        if await aiofiles.os.path.exists(original_savePath) and await aiofiles.os.path.exists(original_savePath_bin):
            await aiofiles.os.rename(original_savePath, newnameFile)
            await aiofiles.os.rename(original_savePath_bin, newnameBin)

def validate_savedirname(savename: str) -> bool:
    return bool(SAVEDIR_RE.fullmatch(savename))

async def parse_pfs_header(pfs_path: str, header: PFSHeader | None = None) -> None | PFSHeader:
    async with aiofiles.open(pfs_path, "rb") as pfs:
        await pfs.seek(0x20)
        basic_block_size = struct.unpack("<I", await pfs.read(0x04))[0]

        await pfs.seek(0x38)
        data_block_count = struct.unpack("<Q", await pfs.read(0x08))[0]

    expected_file_size = basic_block_size * data_block_count
    actual_file_size = await aiofiles.os.path.getsize(pfs_path)

    if expected_file_size != actual_file_size:
        raise OrbisError(f"Expected savesize {expected_file_size} but got {actual_file_size} for file {os.path.basename(pfs_path)}!")

    if header is None:
        header = PFSHeader(basic_block_size, data_block_count, actual_file_size)
        return header
    header.basic_block_size = basic_block_size
    header.data_block_count = data_block_count
    header.size = expected_file_size | actual_file_size

async def parse_sealedkey(keypath: str, key: PfsSKKey | None = None) -> None | PfsSKKey:
    async with aiofiles.open(keypath, "rb") as sealed_key:
        data = bytearray(await sealed_key.read())

    if key is None:
        key = PfsSKKey(data)
        retkey = True
    else:
        key.data = data
        retkey = False

    if not key.validate():
        raise OrbisError(f"Invalid sealed key: {os.path.basename(keypath)}!")
    return key if retkey else None

def sys_files_validator(sys_files: list[str]) -> None:
    n = len(sys_files)
    n_mandatory = len(MANDATORY_SCE_SYS_CONTENTS)
    if n < n_mandatory:
        raise OrbisError("Not enough sce_sys files!")

    n = 0
    for file in sys_files:
        if n == n_mandatory:
            break

        sys_file_name = os.path.basename(file)
        if sys_file_name in MANDATORY_SCE_SYS_CONTENTS:
            n += 1
    if n != n_mandatory:
        raise OrbisError("All mandatory sce_sys files are not present!")
