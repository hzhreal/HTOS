import re
import aiofiles
import os
from .constants import XENO2_TITLEID, FILE_LIMIT_DISCORD, SCE_SYS_CONTENTS, SYS_FILE_MAX
from .extras import generate_random_string
import discord
import asyncio
import struct

SFO_MAGIC = 0x46535000
SFO_VERSION = 0x0101
PARAM_NAME = "param.sfo"

class OrbisError(Exception):
    """Exception raised for errors relating to Orbis."""
    def __init__(self, message: str) -> None:
        self.message = message

class SFOHeader:
    def __init__(self, magic: int, version: int, key_table_offset: int, data_table_offset: int, num_entries: int) -> None:
        self.magic = magic
        self.version = version
        self.key_table_offset = key_table_offset
        self.data_table_offset = data_table_offset
        self.num_entries = num_entries

class SFOIndexTable:
    def __init__(self, key_offset: int, param_format: int, param_length: int, param_max_length: int, data_offset: int) -> None:
        self.key_offset = key_offset
        self.param_format = param_format
        self.param_length = param_length
        self.param_max_length = param_max_length
        self.data_offset = data_offset

class SFOContextParam:
    def __init__(self, key: str, format: int, length: int, max_length: int, actual_length: int, value: bytearray) -> None:
        self.key = key
        self.format = format
        self.length = length
        self.max_length = max_length
        self.actual_length = actual_length
        self.value = value

class SFOContext:
    def __init__(self) -> None:
        self.params = []

    def sfo_read(self, sfo: bytearray) -> int:
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

    def sfo_patch_account_id(self, account_id: str) -> None:
        param = next((param for param in self.params if param.key == "ACCOUNT_ID"), None)
        if param and param.actual_length == 8:
            hexaccid = int(account_id, 16)
            param.value = hexaccid.to_bytes(8, byteorder="little")
        else:
            raise OrbisError("Valid account ID nonexistent in param.sfo!")
        
    def sfo_patch_parameter(self, parameter: str, new_data: bytes) -> None:
        param = next((param for param in self.params if param.key == parameter), None)
        if param and param.max_length > len(new_data):
            param.value = new_data
        else:
            if param: raise OrbisError(f"{parameter} max length ({param.max_length}) exceeded in param.sfo!")
            else: raise OrbisError("Invalid parameter!")

    def sfo_get_param_value(self, parameter: str) -> bytes:
        param_obj = next((param_obj for param_obj in self.params if param_obj.key == parameter), None)
        if param_obj:
            return param_obj.value
        else:
            raise OrbisError("Invalid parameter!")

def checkid(accid: str) -> bool:
    if len(accid) != 16 or not bool(re.match("^[0-9a-fA-F]+$", accid)):
        return False
    else:
        return True
    
def handle_accid(user_id: str) -> str:
    user_id = hex(int(user_id)) # convert decimal to hex
    user_id = user_id[2:] # remove 0x
    user_id = user_id.zfill(16) # pad to 16 length with zeros

    return user_id
    
async def checkSaves(ctx: discord.ApplicationContext, attachments: discord.message.Attachment, ps_save_pair_upload: bool, sys_files: bool) -> list:
    valid_files = []
    if ps_save_pair_upload:
        valid_files = await save_pair_check(ctx, attachments)
        return valid_files

    for attachment in attachments:
        if attachment.size > FILE_LIMIT_DISCORD:
            embFileLarge = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file size of '{attachment.filename}' exceeds the limit of {int(FILE_LIMIT_DISCORD / 1024 / 1024)} MB.",
                    colour=0x854bf7)

            embFileLarge.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
            embFileLarge.set_footer(text="Made with expertise by HTOP")
            await ctx.edit(embed=embFileLarge)
            await asyncio.sleep(1)
    
        elif sys_files and (attachment.filename not in SCE_SYS_CONTENTS or attachment.size > SYS_FILE_MAX):
            embnvSys = discord.Embed(title="Upload alert: Error",
                description=f"{attachment.filename} is not a valid sce_sys file!",
                colour=0x854bf7)
            embnvSys.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
            embnvSys.set_footer(text="Made with expertise by HTOP")
            await ctx.edit(embed=embnvSys)
            await asyncio.sleep(1)
        
        else: valid_files.append(attachment)
    
    return valid_files

async def save_pair_check(ctx: discord.ApplicationContext, attachments: discord.message.Attachment) -> list:
    valid_attachments_check1 = []
    for attachment in attachments:
        filename = attachment.filename
        size = attachment.size
        if filename.endswith(".bin"):
            if size != 96:
                embnvBin = discord.Embed(title="Upload alert: Error",
                    description=f"Sorry, the file size of '{filename}' is not 96 bytes.",
                    colour=0x854bf7)
                embnvBin.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                embnvBin.set_footer(text="Made with expertise by HTOP")
                await ctx.edit(embed=embnvBin)
                await asyncio.sleep(1)
            else:
                valid_attachments_check1.append(attachment)
        else:
            if size > FILE_LIMIT_DISCORD:
                embFileLarge = discord.Embed(title="Upload alert: Error",
                        description=f"Sorry, the file size of '{filename}' exceeds the limit of {int(FILE_LIMIT_DISCORD / 1024 / 1024)} MB.",
                        colour=0x854bf7)
                embFileLarge.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
                embFileLarge.set_footer(text="Made with expertise by HTOP")
                await ctx.edit(embed=embFileLarge)
                await asyncio.sleep(1)
            else:
                valid_attachments_check1.append(attachment)
    
    valid_attachments_final = []
    for attachment in valid_attachments_check1:
        filename = attachment.filename
        if filename.endswith(".bin"): # look for corresponding file

            for attachment_nested in valid_attachments_check1:
                filename_nested = attachment_nested.filename
                if filename_nested == filename: continue

                elif filename_nested == os.path.splitext(filename)[0]:
                    valid_attachments_final.append(attachment)
                    valid_attachments_final.append(attachment_nested)
                    break
    
    return valid_attachments_final 

async def obtainCUSA(param_path: str) -> str | None:
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
    return bool(re.match(r'^CUSA\d{5}$', titleid))

async def resign(paramPath: str, account_id: str) -> None:
    async with aiofiles.open(paramPath, "r+b") as file_param:
        sfo_data = bytearray(await file_param.read())

    context = SFOContext()
    context.sfo_read(sfo_data)
    context.sfo_patch_account_id(account_id)
    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data)

async def reregion_write(paramPath: str, title_id: str) -> None:
    title_id_bytes = title_id.encode("utf-8")
    async with aiofiles.open(paramPath, "rb") as file_param:
       sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)
    context.sfo_patch_parameter("TITLE_ID", title_id_bytes)

    if title_id in XENO2_TITLEID:
        newname = title_id + "01"
        newnameBytes = newname.encode("utf-8")
        context.sfo_patch_parameter("SAVEDATA_DIRECTORY", newnameBytes)
    
    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data) 

async def obtainID(paramPath: str) -> str | None:
    paramPath = os.path.join(paramPath, PARAM_NAME)
    
    async with aiofiles.open(paramPath, "rb") as file_param:
        sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)
    accid_data = context.sfo_get_param_value("ACCOUNT_ID")
    account_id = hex(int.from_bytes(accid_data, byteorder="little"))[2:]
   
    if not checkid(account_id):
        raise OrbisError("Invalid account ID in param.sfo!")

    return account_id

def xeno2Check(title_id: str, savePath: str, original_savePath: str, original_savePath1: str) -> None:
    if title_id in XENO2_TITLEID:
        newnameFile = os.path.join(savePath, title_id + "01")
        newnameBin = os.path.join(savePath, title_id + "01.bin")
        if os.path.exists(newnameFile) and os.path.exists(newnameBin):
            randomString = generate_random_string(5)
            newnameFile = os.path.join(savePath, title_id + f"01_{randomString}")
            newnameBin = os.path.join(savePath, title_id + f"01_{randomString}.bin")
        if os.path.exists(original_savePath) and os.path.exists(original_savePath1):
            os.rename(original_savePath, newnameFile)
            os.rename(original_savePath1, newnameBin)

async def handleTitles(paramPath: str, account_id: str, maintitle: str, subtitle: str) -> None:
    paramPath = os.path.join(paramPath, PARAM_NAME)
    toPatch = {"MAINTITLE": maintitle, "SUBTITLE": subtitle}
    # maintitle or subtitle may be None because the user can choose one or both to edit, therefore we remove the key that is None
    toPatch = {key: value for key, value in toPatch.items() if value != ""}
 
    async with aiofiles.open(paramPath, "rb") as file_param:
        sfo_data = bytearray(await file_param.read())
    
    context = SFOContext()
    context.sfo_read(sfo_data)

    for key in toPatch:
        context.sfo_patch_parameter(key, toPatch[key].encode("utf-8"))

    context.sfo_patch_account_id(account_id)

    new_sfo_data = context.sfo_write()

    async with aiofiles.open(paramPath, "wb") as file_param:
        await file_param.write(new_sfo_data)
