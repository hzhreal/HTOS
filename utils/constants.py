import os
import discord
import logging.config
import re
import errno
import time
from zipfile import (
    #ZIP_BZIP2,
    #ZIP_DEFLATED,
    #ZIP_LZMA,
    ZIP_STORED
)
from sys import argv
from discord.ext import commands
from psnawp_api import PSNAWP
from utils.conversions import mb_to_bytes, saveblocks_to_bytes, minutes_to_seconds, bytes_to_mb

VERSION = "v2.1.0"

# LOGGER
def setup_logger(path: str, logger_type: str, level: str) -> logging.Logger:
    dirname = os.path.dirname(path)

    if not os.path.exists(dirname):
        os.makedirs(dirname)
    if not os.path.exists(path):
        with open(path, "w"):
            ...

    logger = logging.getLogger(logger_type)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
                "datefmt": "%Y-%m-%d - %H:%M:%S%z"
            }
        },
        "handlers": {
            logger_type: {
                "class": "logging.handlers.RotatingFileHandler",
                "level": level,
                "formatter": "detailed",
                "filename": path,
                "maxBytes": 25 * 1024 * 1024,
                "backupCount": 3
            }
        },
        "loggers": {
            logger_type: {
                "level": level,
                "handlers": [
                    logger_type
                ]
            }
        }
    }
    logging.config.dictConfig(config=logging_config)

    return logger

script_name = os.path.splitext(os.path.basename(argv[0]))[0]

if script_name == "bot" or script_name == "app":
    logger = setup_logger(os.path.join("logs", "HTOS.log"), "HTOS_LOGS", "ERROR")
    blacklist_logger = setup_logger(os.path.join("logs", "BLACKLIST.log"), "BLACKLIST_LOGS", "INFO")
else:
    logger = logging.getLogger("null")
    logger.addHandler(logging.NullHandler())
    blacklist_logger = logger

# CONFIG
IP = str(os.getenv("IP"))
PORT_FTP = int(os.getenv("FTP_PORT"))
PORT_CECIE = int(os.getenv("CECIE_PORT"))
MOUNT_LOCATION = str(os.getenv("MOUNT_PATH"))
PS_UPLOADDIR = str(os.getenv("UPLOAD_PATH"))
STORED_SAVES_FOLDER = str(os.getenv("STORED_SAVES_FOLDER_PATH"))
APP_PROFILES_PATH = "profiles.json"
APP_SETTINGS_PATH = "settings.json"
UPLOAD_ENCRYPTED = os.path.join("UserSaves", "uploadencrypted")
UPLOAD_DECRYPTED = os.path.join("UserSaves", "uploaddecrypted")
DOWNLOAD_ENCRYPTED = os.path.join("UserSaves", "downloadencrypted")
PNG_PATH = os.path.join("UserSaves", "png")
PARAM_PATH = os.path.join("UserSaves", "param")
DOWNLOAD_DECRYPTED = os.path.join("UserSaves", "downloaddecrypted")
KEYSTONE_PATH = os.path.join("UserSaves", "keystone")
RANDOMSTRING_LENGTH = 10
DATABASENAME_THREADS = "valid_threads.db"
DATABASENAME_ACCIDS = "account_ids.db"
DATABASENAME_BLACKLIST = "blacklist.db"
TOKEN = str(os.getenv("TOKEN"))
# how to obtain NPSSO:
# go to playstation.com and login
# go to this link https://ca.account.sony.com/api/v1/ssocookie
# find {"npsso":"<64 character npsso code>"}

# if you leave it None the psn.flipscreen.games website will be used to obtain account ID
class NPSSO:
    def __init__(self) -> None:
        self.val: str = str(os.getenv("NPSSO"))
NPSSO_global = NPSSO()

if os.path.basename(argv[0]) == "bot.py":
    if NPSSO_global.val:
        psnawp = PSNAWP(NPSSO_global)
        print("psnawp initialized")
    else:
        psnawp = None
        print("It is recommended that you register a NPSSO token.")
        time.sleep(3)
else:
    psnawp = None

# BOT INITIALIZATION
activity = discord.Activity(type=discord.ActivityType.listening, name="HTOS database")
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=">", activity=activity, intents=intents)

# TITLE IDS FOR CRYPT HANDLING
GTAV_TITLEID = frozenset(["CUSA00411", "CUSA00419", "CUSA00880"])
RDR2_TITLEID = frozenset(["CUSA03041", "CUSA08519", "CUSA08568", "CUSA15698", "CUSA11081"])
XENO2_TITLEID = frozenset(["CUSA05350", "CUSA05088", "CUSA04904", "CUSA05085", "CUSA05774"])
BL3_TITLEID = frozenset(["CUSA07823", "CUSA08025", "CUSA07823"])
WONDERLANDS_TITLEID = frozenset(["CUSA23766", "CUSA23767"])
NDOG_TITLEID = frozenset([
    "CUSA00557", "CUSA00559", "CUSA00552", "CUSA00556", "CUSA00554", # tlou remastered
    "CUSA00341", "CUSA00917", "CUSA00918", "CUSA04529", "CUSA00912", # uncharted 4
    "CUSA07875", "CUSA09564", "CUSA07737", "CUSA08347", "CUSA08352", # uncharted the lost legacy
    "CUSA03281", "CUSA03335", "CUSA03268", "CUSA03259", # uncharted 2 remastered
    "CUSA03282", "CUSA03260", "CUSA03271", "CUSA03336" # uncharted 3 remastered
])
NDOG_COL_TITLEID = frozenset(["CUSA02344", "CUSA02343", "CUSA02826", "CUSA02320", "CUSA01399"]) # the nathan drake collection
NDOG_TLOU2_TITLEID = frozenset([
    "CUSA07820", "CUSA10249", "CUSA13986", "CUSA14006", "CUSA17954",
    "CUSA17962" # tlou part 2
])
MGSV_TPP_TITLEID = frozenset(["CUSA01140", "CUSA01154", "CUSA01099"])
MGSV_GZ_TITLEID = frozenset(["CUSA00218", "CUSA00211", "CUSA00225"])
REV2_TITLEID = frozenset(["CUSA00924", "CUSA01133", "CUSA01141", "CUSA00804", "CUSA00901", "CUSA00999"])
RE7_TITLEID = frozenset([
    "CUSA03842", "CUSA03962", "CUSA09473", "CUSA09643", "CUSA09993",
    "CUSA03839", "CUSA04927", "CUSA09443", "CUSA09470"
])
RERES_TITLEID = frozenset(["CUSA14122", "CUSA14169", "CUSA16725"])
DL1_TITLEID = frozenset(["CUSA00050", "CUSA02010", "CUSA03991", "CUSA03946", "CUSA00078", "CUSA01090", "CUSA01473"])
DL2_TITLEID = frozenset(["CUSA12555", "CUSA12584", "CUSA28617", "CUSA28743"])
RGG_TITLEID = frozenset(["CUSA32173", "CUSA32174", "CUSA32171"])
DI1_TITLEID = frozenset(["CUSA03291", "CUSA03290", "CUSA03684", "CUSA03685", "CUSA05688"])
DI2_TITLEID = frozenset(["CUSA27043", "CUSA01104", "CUSA35681"])
NMS_TITLEID = frozenset(["CUSA03952", "CUSA04841", "CUSA05777", "CUSA05965"])
TERRARIA_TITLEID = frozenset(["CUSA00737", "CUSA00740", "CUSA01616"])
SMT5_TITLEID = frozenset(["CUSA42697", "CUSA42698", "CUSA42502", "CUSA42315"])
RCUBE_TITLEID = frozenset(["CUSA16074", "CUSA27390"])
DSR_TITLEID = frozenset(["CUSA08432", "CUSA08692", "CUSA08495", "CUSA08526"])
RE4R_TITLEID = frozenset(["CUSA33388", "CUSA33387", "CUSA35714", "CUSA33389", "CUSA40600", "CUSA35714", "CUSA40603"])
RE3R_TITLEID = frozenset(["CUSA14278", "CUSA14168", "CUSA14123", "CUSA14129", "CUSA14881", "CUSA16723", "CUSA16724"])
RE2R_TITLEID = frozenset(["CUSA09171", "CUSA12590", "CUSA12497", "CUSA09171", "CUSA09161", "CUSA09193"])
DIGIMON_TITLEID = frozenset(["CUSA06263", "CUSA05392", "CUSA05469"])
SDEW_TITLEID = frozenset(["CUSA06829", "CUSA13911", "CUSA06840", "CUSA26625"])
NIOH2_TITLEID = frozenset(["CUSA15532", "CUSA15526", "CUSA16157"])
MINECRAFT_TITLEID = frozenset([
    "CUSA17401", "CUSA20050", "CUSA17472", "CUSA19622", "CUSA17382", "CUSA00744", "CUSA00265",
    "CUSA00283", "CUSA02169", "CUSA17908"
])
MHWI_TITLEID = frozenset([
    "CUSA15919", "CUSA15825", "CUSA09554", "CUSA07708", "CUSA06027", "CUSA07713"
])
RE_VILLAGE_TITLEID = frozenset([
    "CUSA35037", "CUSA35040", "CUSA18017", "CUSA18008", "CUSA18023",
    "CUSA26891", "CUSA18468", "CUSA18045"
])
LA_NOIRE_TITLEID = frozenset(["CUSA09084", "CUSA10021", "CUSA09172"])

def verify_titleids() -> None:
    from utils.orbis import check_titleid
    title_ids = frozenset([
        GTAV_TITLEID, RDR2_TITLEID, XENO2_TITLEID, BL3_TITLEID, WONDERLANDS_TITLEID, NDOG_TITLEID, NDOG_COL_TITLEID, NDOG_TLOU2_TITLEID,
        MGSV_TPP_TITLEID, MGSV_GZ_TITLEID, REV2_TITLEID, RE7_TITLEID, RERES_TITLEID, DL1_TITLEID, DL2_TITLEID, RGG_TITLEID, DI1_TITLEID,
        DI2_TITLEID, NMS_TITLEID, TERRARIA_TITLEID, SMT5_TITLEID, RCUBE_TITLEID, DSR_TITLEID, RE4R_TITLEID, RE3R_TITLEID, RE2R_TITLEID,
        DIGIMON_TITLEID, SDEW_TITLEID, NIOH2_TITLEID, MINECRAFT_TITLEID, MHWI_TITLEID, RE_VILLAGE_TITLEID, LA_NOIRE_TITLEID
    ])
    for ts in title_ids:
        for t in ts:
            assert check_titleid(t), t
SPECIAL_REREGION_TITLEIDS = frozenset.union(XENO2_TITLEID, MGSV_GZ_TITLEID, MGSV_TPP_TITLEID, MINECRAFT_TITLEID)

# BOT CONFIG
FILE_LIMIT_DISCORD = mb_to_bytes(500) # discord file limit for nitro users
SYS_FILE_MAX = mb_to_bytes(1) # sce_sys files are not that big so 1 MB, keep this low
MAX_FILES = 100
UPLOAD_TIMEOUT = minutes_to_seconds(10) # seconds, how long the user has to upload files or send google drive folder link
OTHER_TIMEOUT = minutes_to_seconds(5) # seconds, how long the user has for button clicks, responding to quickresign command, and responding with account id
GENERAL_TIMEOUT = None # seconds, how long files can actually be downloaded and uploaded for, before timing out
GENERAL_CHUNKSIZE = mb_to_bytes(32)
COMMAND_COOLDOWN = 30 # seconds, for all general commands
BOT_DISCORD_UPLOAD_LIMIT = mb_to_bytes(10) # 10 mb maximum when not considering boost levels
ZIPFILE_COMPRESSION_MODE = ZIP_STORED # check the imports for all modes
ZIPFILE_COMPRESSION_LEVEL = None # change this only if you know the range for the chosen mode
CREATESAVE_ENC_CHECK_LIMIT = 20 # if the amount of gamesaves uploaded in createsave command is less or equal to this number we will perform a check on each of the files to see if we can add encryption to it

PS_ID_DESC = "Your Playstation Network username. Do not include if you want to use the previous one."
IGNORE_SECONDLAYER_DESC = "If you want the bot to neglect checking if the files inside your save can be encrypted/compressed."
SHARED_GD_LINK_DESC = "A link to your shared Google Drive folder, if you want the bot to upload the file to your drive."

BASE_ERROR_MSG = "An unexpected server-side error has occurred! Try again, and if it occurs multiple times, please contact the host."

BLACKLIST_MESSAGE = "YOU HAVE BEEN DENIED!"

ZIPOUT_NAME = ("PS4", ".zip") # name, ext

# ORBIS CONSTANTS THAT DOES NOT NEED TO BE IN orbis.py

SCE_SYS_CONTENTS = frozenset(
    ["param.sfo", "icon0.png", "keystone"] +
    ["sce_icon0png" + str(i) for i in range(10)] +
    ["sce_paramsfo" + str(i) for i in range(10)]
)
MANDATORY_SCE_SYS_CONTENTS = frozenset(["param.sfo", "keystone"])

ICON0_MAXSIZE = 0x1C800
ICON0_FORMAT = (228, 128)
ICON0_NAME = "icon0.png"

KEYSTONE_SIZE = SEALED_KEY_ENC_SIZE = SAVEBLOCKS_MIN = 0x60
KEYSTONE_NAME = "keystone"

PARAM_NAME = "param.sfo"
SCE_SYS_NAME = "sce_sys"

SAVEBLOCKS_MAX = 32768 # SAVESIZE WILL BE SAVEBLOCKS * 2¹⁵
SAVESIZE_MAX = saveblocks_to_bytes(SAVEBLOCKS_MAX)
SAVESIZE_MB_MIN = bytes_to_mb(saveblocks_to_bytes(SAVEBLOCKS_MIN))
SAVESIZE_MB_MAX = bytes_to_mb(SAVESIZE_MAX)

MAX_PATH_LEN = 1024
MAX_FILENAME_LEN = 255

# regex
PSN_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# ERRNO
CON_FAIL = frozenset([errno.ECONNREFUSED, errno.ETIMEDOUT, errno.EHOSTUNREACH, errno.ENETUNREACH])
CON_FAIL_MSG = "PS4 not connected!"

# EMBEDS
EMBED_DESC_LIM = 4096
EMBED_FIELD_LIM = 25
