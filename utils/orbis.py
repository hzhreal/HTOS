import re
import aiofiles
import aiofiles.os
import os
import discord
import asyncio
import struct
from utils.constants import XENO2_TITLEID, MGSV_TPP_TITLEID, MGSV_GZ_TITLEID, FILE_LIMIT_DISCORD, SCE_SYS_CONTENTS, SYS_FILE_MAX, PARAM_NAME, SEALED_KEY_ENC_SIZE, MAX_FILENAME_LEN, PS_UPLOADDIR, MAX_PATH_LEN, Color
from utils.extras import generate_random_string
from data.crypto.mgsv_crypt import Crypt_MGSV
from dataclasses import dataclass
from numpy import uint32

SFO_MAGIC = 0x46535000
SFO_VERSION = 0x0101

SAVEDIR_RE = re.compile(r"^[a-zA-Z0-9\-.\@]+$")
TITLE_ID_RE = re.compile(r"^CUSA\d{5}$")
ACCID_RE = re.compile(r"^[0-9a-fA-F]+$")

class OrbisError(Exception):
    """Exception raised for errors relating to Orbis."""
    def __init__(self, message: str) -> None:
        self.message = message

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
                    value = self.value.decode("utf-8")
                except UnicodeDecodeError:
                    value = hex(int.from_bytes(self.value, byteorder="little"))
            case "CATEGORY" | "DETAIL" | "FORMAT" | "MAINTITLE" | "SAVEDATA_DIRECTORY" | "SUBTITLE" | "TITLE_ID":
                value = self.value.decode("utf-8")
            case "ATTRIBUTE" | "SAVEDATA_LIST_PARAM":
                value = hex(struct.unpack("<I", self.value)[0])
            case "PARAMS" | "SAVEDATA_BLOCKS":
                value = self.value.decode("utf-8", errors="ignore")

        info["converted_value"] = value
        return info

# account_id: uint64
# attribute: uint32
# category: utf-8
# detail: utf-8
# format: utf-8
# maintitle: utf-8
# params: utf-8-s
# savedata_blocks: utf-8-s
# savedata_directory: utf-8
# savedata_list_param: uint32
# subtitle: utf-8
# title_id: utf-8

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
        try: struct.pack_into("<IIIII", sfo, 0, header.magic, header.version, header.key_table_offset, header.data_table_offset, header.num_entries)
        except struct.error: raise OrbisError("Invalid param.sfo!")

        key_offset, data_offset = 0, 0
        for i, param in enumerate(self.params):
            index_offset = 20 + i * 16
            index_table = SFOIndexTable(key_offset, param.format, param.length, param.max_length, data_offset)
            struct.pack_into("<HHIII", sfo, index_offset, index_table.key_offset, index_table.param_format, index_table.param_length, index_table.param_max_length, index_table.data_offset)

            key_offset += len(param.key) + 1
            data_offset += param.actual_length

        for i, param in enumerate(self.params):
            index_table = SFOIndexTable(*struct.unpack("<HHIII", sfo[20 + i * 16: 20 + i * 16 + 16]))
            key_offset = index_table.key_offset
            data_offset = index_table.data_offset
        
            struct.pack_into(f"{len(param.key)+1}s", sfo, header.key_table_offset + key_offset, param.key.encode("utf-8"))
            struct.pack_into(f"{param.actual_length}s", sfo, header.data_table_offset + data_offset, param.value)

        return sfo

    def sfo_patch_account_id(self, account_id: str | int) -> None:
        param: SFOContextParam | None = next((param for param in self.params if param.key == "ACCOUNT_ID"), None)
        if param and param.actual_length == 8:
            if isinstance(account_id, str):
                account_id = int(account_id, 16)
            param.value = struct.pack("<Q", account_id)
        else:
            raise OrbisError("Valid account ID nonexistent in param.sfo!")
        
    def sfo_patch_parameter(self, parameter: str, new_data: str | int) -> None:
        param: SFOContextParam | None = next((param for param in self.params if param.key == parameter), None)
        if not param:
            raise OrbisError("Invalid parameter!")
        
        if isinstance(new_data, int):
            new_data_uint32_t = uint32(new_data)
            new_data_uint32_t = struct.pack("<I", new_data_uint32_t)
            if param.max_length >= len(new_data_uint32_t): 
                param.value = new_data_uint32_t
            else:
                raise OrbisError(f"{parameter} max length ({param.max_length}) exceeded in param.sfo!")
        
        else:
            new_data_utf8 = new_data.encode("utf-8", errors="ignore")
            if param.max_length > len(new_data_utf8): # last byte is for null terminating
                param.value = new_data_utf8
                param.length = len(new_data_utf8) + 1
            else:
                raise OrbisError(f"{parameter} max length ({param.max_length}) exceeded in param.sfo! Remember, last byte is reserved for this parameter.")

    def sfo_get_param_value(self, parameter: str) -> bytes:
        param: SFOContextParam | None = next((param for param in self.params if param.key == parameter), None)
        if param:
            return param.value
        else:
            raise OrbisError("Invalid parameter!")
        
    def sfo_get_param_data(self) -> list[dict[str, str | int | bytearray]]:
        param_data = []
        for param in self.params:
            param: SFOContextParam

            param_data.append(param.as_dict())
        return param_data
    
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
    
async def checkSaves(
          ctx: discord.ApplicationContext, 
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
            embfn = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file name of '{attachment.filename}' ({len(attachment.filename)}) exceeds {MAX_FILENAME_LEN}.",
                    colour=Color.DEFAULT.value)
            embfn.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embfn)
            await asyncio.sleep(1)

        elif attachment.size > FILE_LIMIT_DISCORD:
            embFileLarge = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file size of '{attachment.filename}' exceeds the limit of {int(FILE_LIMIT_DISCORD / 1024 / 1024)} MB.",
                    colour=Color.DEFAULT.value)
            embFileLarge.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embFileLarge)
            await asyncio.sleep(1)
    
        elif sys_files and (attachment.filename not in SCE_SYS_CONTENTS or attachment.size > SYS_FILE_MAX):
            embnvSys = discord.Embed(title="Upload alert: Error",
                description=f"{attachment.filename} is not a valid sce_sys file!",
                colour=Color.DEFAULT.value)
            embnvSys.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embnvSys)
            await asyncio.sleep(1)

        elif total_count > savesize:
            raise OrbisError(f"The files you are uploading for this save exceeds the savesize {savesize}!")
        
        else: 
            total_count += attachment.size
            valid_files.append(attachment)
    
    return valid_files

async def save_pair_check(ctx: discord.ApplicationContext, attachments: list[discord.message.Attachment]) -> list[discord.message.Attachment]:
    """Makes sure the save pair through discord upload is valid."""
    valid_attachments_check1 = []
    for attachment in attachments:
        path_len = len(PS_UPLOADDIR + "/" + attachment.filename + "/")

        if len(attachment.filename) > MAX_FILENAME_LEN:
            embfn = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file name of '{attachment.filename}' ({len(attachment.filename)}) exceeds {MAX_FILENAME_LEN}.",
                    colour=Color.DEFAULT.value)
            embfn.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embfn)
            await asyncio.sleep(1)

        elif path_len > MAX_PATH_LEN:
            embpn = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the path '{attachment.filename}' ({path_len}) will create exceed ({MAX_PATH_LEN}).",
                    colour=Color.DEFAULT.value)
            embpn.set_footer(text="Made by hzh.")
            await ctx.edit(embed=embpn)
            await asyncio.sleep(1)

        elif attachment.filename.endswith(".bin"):
            if attachment.size != SEALED_KEY_ENC_SIZE:
                embnvBin = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file size of '{attachment.filename}' is not {SEALED_KEY_ENC_SIZE} bytes.",
                    colour=Color.DEFAULT.value)
                embnvBin.set_footer(text="Made by hzh.")
                await ctx.edit(embed=embnvBin)
                await asyncio.sleep(1)
            else:
                valid_attachments_check1.append(attachment)
        else:
            if attachment.size > FILE_LIMIT_DISCORD:
                embFileLarge = discord.Embed(title="Upload alert: Error",
                        description=f"Sorry, the file size of '{attachment.filename}' exceeds the limit of {int(FILE_LIMIT_DISCORD / 1024 / 1024)} MB.",
                        colour=Color.DEFAULT.value)
                embFileLarge.set_footer(text="Made by hzh.")
                await ctx.edit(embed=embFileLarge)
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

async def obtainCUSA(param_path: str) -> str:
    """Obtains TITLE_ID from sfo file."""
    param_local_path = os.path.join(param_path, PARAM_NAME)

    async with aiofiles.open(param_local_path, "rb") as file:
        sfo_data = bytearray(await file.read())

    context = SFOContext()
    context.sfo_read(sfo_data)
    data_title_id = context.sfo_get_param_value("TITLE_ID")
    data_title_id = bytearray(filter(lambda x: x != 0x00, data_title_id))

    try: title_id = data_title_id.decode("utf-8")
    except UnicodeDecodeError: raise OrbisError("Invalid title ID in param.sfo!")
    
    if not check_titleid(title_id):
        raise OrbisError("Invalid title id!")
        
    return title_id

def check_titleid(titleid: str) -> bool:
    return bool(TITLE_ID_RE.fullmatch(titleid))

async def resign(paramPath: str, account_id: str) -> None:
    """Traditional resigning."""
    async with aiofiles.open(paramPath, "rb") as file_param:
        sfo_data = bytearray(await file_param.read())

    context = SFOContext()
    context.sfo_read(sfo_data)
    context.sfo_patch_account_id(account_id)
    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data)

async def reregion_write(paramPath: str, title_id: str, decFilesPath: str) -> None:
    """Writes the new title id in the sfo file, changes the SAVEDATA_DIRECTORY for the games needed."""
    async with aiofiles.open(paramPath, "rb") as file_param:
       sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)
    context.sfo_patch_parameter("TITLE_ID", title_id)

    if title_id in XENO2_TITLEID:
        newname = title_id + "01"
        context.sfo_patch_parameter("SAVEDATA_DIRECTORY", newname)
    
    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
        try: 
            await Crypt_MGSV.reregion_changeCrypt(decFilesPath, title_id)
        except (ValueError, IOError, IndexError):
            raise OrbisError("Error changing MGSV crypt!")
        
        newname = Crypt_MGSV.KEYS[title_id]["name"]
        context.sfo_patch_parameter("SAVEDATA_DIRECTORY", newname)
    
    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data) 

async def obtainID(paramPath: str) -> str | None:
    """Obtains accountID from the sfo file."""
    paramPath = os.path.join(paramPath, PARAM_NAME)
    
    async with aiofiles.open(paramPath, "rb") as file_param:
        sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)
    accid_data = context.sfo_get_param_value("ACCOUNT_ID")

    try: 
        account_id = accid_data.decode("utf-8")
        if account_id[:2].lower() == "0x":
           account_id = account_id[2:]
    except UnicodeDecodeError:
        account_id = hex(struct.unpack("<Q", accid_data)[0])[2:]

    if not checkid(account_id):
        raise OrbisError("Invalid account ID in param.sfo!")

    return account_id

async def reregionCheck(title_id: str, savePath: str, original_savePath: str, original_savePath_bin: str) -> None:
    """Renames the save after Re-regioning for the games that need it, random string is appended at the end for no overwriting."""
    if title_id in XENO2_TITLEID:
        newnameFile = os.path.join(savePath, title_id + "01")
        newnameBin = os.path.join(savePath, title_id + "01.bin")
        if await aiofiles.os.path.exists(newnameFile) and await aiofiles.os.path.exists(newnameBin):
            randomString = generate_random_string(5)
            newnameFile = os.path.join(savePath, title_id + f"01_{randomString}")
            newnameBin = os.path.join(savePath, title_id + f"01_{randomString}.bin")
        if await aiofiles.os.path.exists(original_savePath) and await aiofiles.os.path.exists(original_savePath_bin):
            await aiofiles.os.rename(original_savePath, newnameFile)
            await aiofiles.os.rename(original_savePath_bin, newnameBin)

    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_TPP_TITLEID:
        new_regionName = Crypt_MGSV.KEYS[title_id]["name"]
        newnameFile = os.path.join(savePath, new_regionName)
        newnameBin = os.path.join(savePath, new_regionName + ".bin")
        if await aiofiles.os.path.exists(newnameFile) and await aiofiles.os.path.exists(newnameBin):
            randomString = generate_random_string(5)
            newnameFile = os.path.join(savePath, new_regionName + f"_{randomString}")
            newnameBin = os.path.join(savePath, new_regionName + f"_{randomString}.bin")
        if await aiofiles.os.path.exists(original_savePath) and await aiofiles.os.path.exists(original_savePath_bin):
            await aiofiles.os.rename(original_savePath, newnameFile)
            await aiofiles.os.rename(original_savePath_bin, newnameBin)

async def handleTitles(paramPath: str, account_id: str, maintitle: str, subtitle: str) -> None:
    """Used to alter MAINTITLE & SUBTITLE in the sfo file, for the change titles command."""
    paramPath = os.path.join(paramPath, PARAM_NAME)
    toPatch = {"MAINTITLE": maintitle, "SUBTITLE": subtitle}
    # maintitle or subtitle may be None because the user can choose one or both to edit, therefore we remove the key that is an empty str
    toPatch = {key: value for key, value in toPatch.items() if value}
 
    async with aiofiles.open(paramPath, "rb") as file_param:
        sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)

    for key in toPatch:
        context.sfo_patch_parameter(key, toPatch[key])

    context.sfo_patch_account_id(account_id)

    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data)

def validate_savedirname(savename: str) -> bool:
    return bool(SAVEDIR_RE.fullmatch(savename))

# Thanks to https://github.com/B-a-t-a-n-g for showing me how to parse the header
async def parse_pfs_header(pfs_path: str) -> dict[str, int]:
    async with aiofiles.open(pfs_path, "rb") as pfs:
        await pfs.seek(0x20)
        basic_block_size = struct.unpack("<I", await pfs.read(0x04))[0]

        await pfs.seek(0x38)
        data_block_count = struct.unpack("<Q", await pfs.read(0x08))[0]

    expected_file_size = basic_block_size * data_block_count
    actual_file_size = await aiofiles.os.path.getsize(pfs_path)

    if expected_file_size != actual_file_size:
        raise OrbisError(f"Expected savesize {expected_file_size} but got {actual_file_size} for file {os.path.basename(pfs_path)}!")

    pfs_header = {
        "basic_block_size": basic_block_size,
        "data_block_count": data_block_count,
        "size": expected_file_size | actual_file_size
    }
    return pfs_header