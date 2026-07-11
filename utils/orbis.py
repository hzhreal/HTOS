import re
import aiofiles
import aiofiles.os
import os
import struct
import shutil
from enum import Enum
from dataclasses import dataclass
from Crypto.Cipher import AES

from data.crypto.helpers import extra_reregion_pre, extra_reregion_pre_needs_folder, extra_reregion_post
from network.ftp_functions import FTPps
from network.socket_functions import SocketPS
from utils.constants import (
    MOUNT_LOCATION, MANDATORY_SCE_SYS_CONTENTS, SCE_SYS_NAME, MAX_FILENAME_LEN, MAX_PATH_LEN,
    RANDOMSTRING_LENGTH, PS_UPLOADDIR
)
from utils.extras import obtain_savenames, completed_print
from utils.type_helpers import uint32, uint64, utf_8, utf_8_s, TypeCategory
from utils.workspace import enumerate_files
from utils.exceptions import OrbisError
from utils.conversions import bytes_to_saveblocks, mb_to_bytes, saveblocks_to_bytes, round_half_up

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
        savepath = await self.batch.fInstance.dlencrypted_bulk(self.batch.user_id, self.realSave, self.title_id)
        if self.reregion_check:
            sp = await extra_reregion_post(savepath, self.title_id)
            if sp is not None:
                savepath = sp
        await fix_pfs_auth_code_info(savepath)

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
        if extra_reregion_pre_needs_folder(self.title_id):
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
                    if accid.value.startswith("0x"):
                        if not checkid(accid.value[2:]):
                            raise OrbisError("Invalid!")
                    else:
                        if not checkid(accid.value):
                            raise OrbisError("Invalid!")
                    value = accid.value
                except (UnicodeDecodeError, OrbisError):
                    accid = uint64(self.value, "little")
                    value = "0x" + hex(accid.value)[2:].zfill(16)
            case "SAVEDATA_BLOCKS":
                blocks = uint64(self.value, "little")
                value = hex(blocks.value)
            case "CATEGORY" | "DETAIL" | "FORMAT" | "MAINTITLE" | "SAVEDATA_DIRECTORY" | "SUBTITLE" | "TITLE_ID":
                ctx = utf_8(self.value)
                value = ctx.to_str()
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
        self.params: list[SFOContextParam] = []

    def sfo_read(self, sfo: bytearray) -> None:
        sfo_len = len(sfo)
        if sfo_len < 20:
            raise OrbisError("Invalid param.sfo size!")

        header_data = struct.unpack("<IIIII", sfo[:20])
        header = SFOHeader(*header_data)

        if header.magic != SFO_MAGIC:
            raise OrbisError("Invalid param.sfo header magic!")

        if header.num_entries > 12:
            raise OrbisError("The param.sfo has too many entries!")

        total_entry_sizes = 0
        try:
            for i in range(header.num_entries):
                index_offset = 20 + i * 16
                index_data = struct.unpack("<HHIII", sfo[index_offset:index_offset + 16])
                index_table = SFOIndexTable(*index_data)

                param_offset = header.key_table_offset + index_table.key_offset
                key_end = sfo.find(b"\x00", param_offset)
                if key_end == -1 or param_offset > key_end:
                    raise OrbisError("")
                param_key = sfo[param_offset:key_end].decode("utf-8")

                param_data_offset = header.data_table_offset + index_table.data_offset
                if param_data_offset + index_table.param_max_length > sfo_len:
                    raise OrbisError("")
                total_entry_sizes += index_table.param_max_length
                if total_entry_sizes > sfo_len:
                    raise OrbisError("")
                param_data = sfo[param_data_offset:param_data_offset + index_table.param_max_length]

                param = SFOContextParam(key=param_key, format=index_table.param_format,
                                        length=index_table.param_length, max_length=index_table.param_max_length,
                                        value=param_data, actual_length=index_table.param_max_length)

                self.params.append(param)
        except (struct.error, UnicodeDecodeError, IndexError, OrbisError):
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
            struct.pack_into(
                "<IIIII",
                sfo, 0, header.magic, header.version, header.key_table_offset, header.data_table_offset, header.num_entries
            )
        except struct.error:
            raise OrbisError("Failed to generate a param.sfo!")

        key_offset, data_offset = 0, 0
        for i, param in enumerate(self.params):
            index_offset = 20 + i * 16
            index_table = SFOIndexTable(key_offset, param.format, param.length, param.max_length, data_offset)

            try:
                struct.pack_into(
                    "<HHIII",
                    sfo, index_offset, index_table.key_offset, index_table.param_format,
                    index_table.param_length, index_table.param_max_length, index_table.data_offset
                )
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
        param: SFOContextParam | None = next((param for param in self.params if param.key == parameter), None)
        if not param:
            raise OrbisError(f"Invalid parameter: {parameter}!")

        param_type: uint32 | uint64 | utf_8 | utf_8_s | None = SFO_TYPES.get(parameter)
        if not param_type:
            raise OrbisError(f"Unsupported parameter: {parameter}!")

        if param_type.CATEGORY == TypeCategory.INTEGER:
            ctx = type(param_type)(new_data, "little")
        else:
            ctx = type(param_type)(new_data)

        max_len = param.max_length

        if ctx.CATEGORY == TypeCategory.CHARACTER:
            ctx: utf_8 | utf_8_s
            if ctx.bytelen >= max_len:
               raise OrbisError(
                    f"The parameter: {parameter} reached the max length it has of {max_len}! "
                    "Remember last byte is reserved for null termination for this parameter."
                )
            v = ctx.to_cstr()
            l = len(v)
        else:
            if ctx.bytelen > max_len:
                raise OrbisError(f"The parameter: {parameter} reached the max length it has of {max_len}!")
            v = ctx.as_bytes
            l = ctx.bytelen

        param.length = l
        param.value = v

    def sfo_get_param_value(self, parameter: str) -> int | str:
        param: SFOContextParam | None = next((param for param in self.params if param.key == parameter), None)
        if not param:
            raise OrbisError(f"Missing sfo parameter: {parameter}!")

        param_type: uint32 | uint64 | utf_8 | utf_8_s | None = SFO_TYPES.get(parameter)
        try:
            if param_type.CATEGORY == TypeCategory.INTEGER:
                v = type(param_type)(param.value, "little").value
            else:
                v = type(param_type)(param.value).to_str()
        except ValueError:
            raise OrbisError(f"Invalid sfo parameter value for {parameter}!")
        return v

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
    if accid.lower().startswith("0x"):
        accid = accid[2:]
    return len(accid) == 16 and bool(ACCID_RE.fullmatch(accid))

def handle_accid(user_id: str) -> str:
    user_id = hex(int(user_id)) # convert decimal to hex
    user_id = user_id[2:] # remove 0x
    user_id = user_id.zfill(16) # pad to 16 length with zeros

    return user_id

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

    title_id = ctx.sfo_get_param_value("TITLE_ID")
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

    ctx.sfo_patch_parameter("TITLE_ID", title_id)
    savepairname = ctx.sfo_get_param_value("SAVEDATA_DIRECTORY")
    new_name = await extra_reregion_pre(dec_files_folder, title_id, savepairname)
    if new_name:
        ctx.sfo_patch_parameter("SAVEDATA_DIRECTORY", new_name)

def is_valid_savedirname(savename: str) -> bool:
    return bool(SAVEDIR_RE.fullmatch(savename))

def validate_savedirname(savename: str) -> None:
    if not bool(SAVEDIR_RE.fullmatch(savename)):
        raise OrbisError("Invalid savename!")

def get_savedirname_filename_len(savename: str) -> int:
    filename_bin = f"{savename}.bin_{'X' * RANDOMSTRING_LENGTH}"
    return len(filename_bin)

def get_savedirname_path_len(savename: str) -> int:
    filename_bin = f"{savename}.bin_{'X' * RANDOMSTRING_LENGTH}"
    path = PS_UPLOADDIR + "/" + filename_bin + "/"
    return len(path)

def get_path_len(rel_path: str) -> int:
    path = MOUNT_LOCATION + f"/{'X' * RANDOMSTRING_LENGTH}/" + rel_path + "/"
    return len(path)

def validate_savedirname_path(savename: str) -> None:
    filename_bin_len = get_savedirname_filename_len(savename)
    path_len = get_savedirname_path_len(savename)

    if filename_bin_len > MAX_FILENAME_LEN:
        raise OrbisError(f"The length of the savename will exceed {MAX_FILENAME_LEN}!")
    if path_len > MAX_PATH_LEN:
        raise OrbisError(f"The length of the path the save creates will exceed {MAX_PATH_LEN}!")

async def parse_pfs_header(pfs_path: str, header: PFSHeader | None = None) -> None | PFSHeader:
    async with aiofiles.open(pfs_path, "rb") as pfs:
        await pfs.seek(0x20)
        basic_block_size = struct.unpack("<I", await pfs.read(0x04))[0]

        await pfs.seek(0x38)
        data_block_count = struct.unpack("<Q", await pfs.read(0x08))[0]

    if basic_block_size != 0x8_000:
        raise OrbisError("Unsupported pfs block size!")

    expected_file_size = basic_block_size * data_block_count
    actual_file_size = await aiofiles.os.path.getsize(pfs_path)

    if expected_file_size != actual_file_size:
        raise OrbisError(f"Expected savesize {expected_file_size} but got {actual_file_size} for file {os.path.basename(pfs_path)}!")

    if header is None:
        header = PFSHeader(basic_block_size, data_block_count, actual_file_size)
        return header
    header.basic_block_size = basic_block_size
    header.data_block_count = data_block_count
    header.size = actual_file_size

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

async def fix_pfs_auth_code_info(path: str) -> None:
    # we may assume that the savefile is valid (it has been processed by the console)
    HDR_HASH_OFF            = 0x380
    HDR_HASH_SIZE           = 0x20

    AUTH_CODE_OFF           = 0x7F90
    AUTH_CODE_HDR_HASH2_OFF = AUTH_CODE_OFF + 0x40
    AUTH_CODE_SIZE          = 0x70

    AUTH_CODE_MAGIC = bytes([
        0x79, 0x2B, 0x1A, 0xC1, 0xBB, 0x9B, 0x9A, 0x45
    ])
    KEY = bytes([
        0x2B, 0xCF, 0x69, 0x8E, 0x79, 0xCF, 0xDD, 0xFA,
        0xC2, 0x4D, 0x4C, 0x25, 0xBF, 0x35, 0x1E, 0x62
    ])

    async with aiofiles.open(path, "r+b") as pfs:
        await pfs.seek(AUTH_CODE_OFF)
        magic = await pfs.read(len(AUTH_CODE_MAGIC))
        if magic != AUTH_CODE_MAGIC:
            return

        await pfs.seek(HDR_HASH_OFF)
        hash = await pfs.read(HDR_HASH_SIZE)

        # we can start in the middle of the ciphertext
        await pfs.seek(AUTH_CODE_HDR_HASH2_OFF - 16)
        chunk = await pfs.read(16 + AUTH_CODE_SIZE - (AUTH_CODE_HDR_HASH2_OFF - AUTH_CODE_OFF))
        iv = chunk[:16]
        chunk = bytearray(chunk[16:])

        AES.new(KEY, AES.MODE_CBC, iv).decrypt(chunk, chunk)
        # fix pfs_hdr_hash2
        chunk[:HDR_HASH_SIZE] = hash
        # make sure copy_ctr is nonzero
        if chunk[HDR_HASH_SIZE:HDR_HASH_SIZE + 8] == bytes(8):
            chunk[HDR_HASH_SIZE:HDR_HASH_SIZE + 8] = b"\x01\x00\x00\x00\x00\x00\x00\x00"
        AES.new(KEY, AES.MODE_CBC, iv).encrypt(chunk, chunk)

        await pfs.seek(AUTH_CODE_HDR_HASH2_OFF)
        await pfs.write(chunk)

def compute_saveblocks(total_folder_size: int) -> int:
    n = total_folder_size

    n = max(n, mb_to_bytes(3))

    n = round_half_up(n * 1.1) + mb_to_bytes(2)
    block = saveblocks_to_bytes(1)
    r = block - n % block
    if r != 0:
        n += r

    return bytes_to_saveblocks(n)

