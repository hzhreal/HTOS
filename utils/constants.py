from dotenv import load_dotenv
import os
import discord
from discord.ext import commands

load_dotenv()

activity = discord.Activity(type=discord.ActivityType.listening, name="HTOS database")
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=">", activity=activity, intents=intents)
change_group = discord.SlashCommandGroup("change")

IP = str(os.getenv("IP"))
PORT = int(os.getenv("FTP_PORT"))
PORTSOCKET = int(os.getenv("SOCKET_PORT"))
MOUNT_LOCATION = str(os.getenv("MOUNT_PATH"))
PS_UPLOADDIR = str(os.getenv("UPLOAD_PATH"))
STORED_SAVES_FOLDER = str(os.getenv("STORED_SAVES_FOLDER_PATH"))
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
NPSSO = os.getenv("NPSSO") 
# how to obtain NPSSO:
# go to playstation.com and login
# go to this link https://ca.account.sony.com/api/v1/ssocookie
# find {"npsso":"<64 character npsso code>"}

# if you leave it None the psn.flipscreen.games website will be used to obtain account ID

GTAV_TITLEID = ["CUSA00411", "CUSA00419", "CUSA00880"] 
RDR2_TITLEID = ["CUSA03041", "CUSA08519", "CUSA08568", "CUSA15698"]
XENO2_TITLEID = ["CUSA05350", "CUSA05088", "CUSA04904", "CUSA05085", "CUSA05774"]
BL3_TITLEID = ["CUSA07823", "CUSA08025"]
WONDERLANDS_TITLEID = ["CUSA23766", "CUSA23767"]
NDOG_TITLEID = ["CUSA00557", "CUSA00559", "CUSA00552", "CUSA00556", "CUSA00554"] # tlou remastered
MGSV_TPP_TITLEID = ["CUSA01140", "CUSA01154", "CUSA01099"]
MGSV_GZ_TITLEID = ["CUSA00218", "CUSA00211", "CUSA00225"]
REV2_TITLEID = ["CUSA00924", "CUSA01133", "CUSA01141", "CUSA00804"]

FILE_LIMIT_DISCORD = 500 * 1024 * 1024  # 500 MB, discord file limit
SYS_FILE_MAX = 1 * 1024 * 1024 # sce_sys files are not that big so 1 MB
MAX_FILES = 100
UPLOAD_TIMEOUT = 600 # seconds, for uploading files or google drive folder link
OTHER_TIMEOUT = 300 # seconds, for button click, responding to quickresign command, and responding with account id
BOT_DISCORD_UPLOAD_LIMIT = 25 # 25 mb minimum when no nitro boosts in server

SCE_SYS_CONTENTS = ["param.sfo", "icon0.png", "keystone", "sce_icon0png1", "sce_paramsfo1"]

PS_ID_DESC = "Your Playstation Network username. Do not include if you want to use the previous one."

embUtimeout = discord.Embed(title="Upload alert: Error",
                      description="Time's up! You didn't attach any files.",
                      colour=0x854bf7)
embUtimeout.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embUtimeout.set_footer(text="Made with expertise by HTOP")

embgdt = discord.Embed(title="Google drive upload: Error",
                      description="You did not respond with the link in time!",
                      colour=0x854bf7)
embgdt.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embgdt.set_footer(text="Made with expertise by HTOP")

emb6 = discord.Embed(title="Upload alert: Error",
                      description="You did not upload 2 savefiles in one response to the bot, or you uploaded invalid files!",
                      colour=0x854bf7)
emb6.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb6.set_footer(text="Made with expertise by HTOP")

embhttp = discord.Embed(title="HttpError",
                                description="Are you sure that you uploaded binary content?",
                                colour=0x854bf7)
embhttp.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embhttp.set_footer(text="Made with expertise by HTOP")

embEncrypted1 = discord.Embed(title="Resigning process: Encrypted",
                      description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                      colour=0x854bf7)
embEncrypted1.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embEncrypted1.set_footer(text="Made with expertise by HTOP")

embDecrypt1 = discord.Embed(title="Decrypt Process",
                      description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                      colour=0x854bf7)
embDecrypt1.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embDecrypt1.set_footer(text="Made with expertise by HTOP")

emb12 = discord.Embed(title="Decrypt process: Downloading",
                      description="Save mounted, downloading decrypted savefile.",
                      colour=0x854bf7) 
emb12.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb12.set_footer(text="Made with expertise by HTOP")

emb14 = discord.Embed(title="Resigning process: Decrypted",
                      description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                      colour=0x854bf7)
emb14.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb14.set_footer(text="Made with expertise by HTOP")

emb17 = discord.Embed(title="Resigning Process (Decrypted): Initializing",
                      description="Mounting save.",
                      colour=0x854bf7) 
emb17.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb17.set_footer(text="Made with expertise by HTOP")

emb20 = discord.Embed(title="Re-region process: Upload encrypted files from the FOREIGN region",
                      description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                      colour=0x854bf7)

emb20.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb20.set_footer(text="Made with expertise by HTOP")
emb4 = discord.Embed(title="Resigning process: Encrypted",
                    description="Your save is being resigned, please wait...",
                    colour=0x854bf7)

emb4.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb4.set_footer(text="Made with expertise by HTOP")
emb21 = discord.Embed(title="Re-region process: Upload encrypted files from YOUR region",
                    description="Please attach two encrypted savefiles that you want to upload (.bin and non bin).",
                    colour=0x854bf7)

emb21.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb21.set_footer(text="Made with expertise by HTOP")

emb22 = discord.Embed(title="Obtain process: Keystone",
                          description="Obtaining keystone, please wait...",
                          colour=0x854bf7)
emb22.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb22.set_footer(text="Made with expertise by HTOP")

embpng = discord.Embed(title="PNG Process",
                      description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                      colour=0x854bf7)
embpng.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embpng.set_footer(text="Made with expertise by HTOP")

embpng1 = discord.Embed(title="PNG process: Initializing",
                      description="Mounting save.",
                      colour=0x854bf7) 
embpng1.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embpng1.set_footer(text="Made with expertise by HTOP")

embpng2 = discord.Embed(title="PNG process: Downloading",
                    description="Save mounted",
                    colour=0x854bf7)
embpng2.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embpng2.set_footer(text="Made with expertise by HTOP")

embnv1 = discord.Embed(title="Error: PS username not valid",
                      description="This PS username is not in a valid format.",
                      colour=0x854bf7)

embnv1.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embnv1.set_footer(text="Made with expertise by HTOP")

emb8 = discord.Embed(title="Error: PSN username",
                description="Your input was not a valid PSN username, you have 60 seconds to reply with your account ID instead.",
                colour=0x854bf7)
emb8.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb8.set_footer(text="Made with expertise by HTOP")

embnt = discord.Embed(title="Error: Time limit reached",
                    description="You did not send your account ID in time.",
                    colour=0x854bf7)
embnt.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embnt.set_footer(text="Made with expertise by HTOP")

embvalidpsn = discord.Embed(title="Obtained: PSN username",
                    description="Your input was a valid PSN username.",
                    colour=0x854bf7)
embvalidpsn.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embvalidpsn.set_footer(text="Made with expertise by HTOP")

embinit = discord.Embed(title="Instance creator",
                                description="Click button to get started!\nYou can also use old threads that you have created with the bot.",
                                colour=0x854bf7)
embinit.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embinit.set_footer(text="Made with expertise by HTOP")

embTitleChange = discord.Embed(title="Change title: Upload",
                                description="Please attach atleast two encrypted savefiles that you want to upload (.bin and non bin).",
                                colour=0x854bf7)
embTitleChange.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embTitleChange.set_footer(text="Made with expertise by HTOP")

embTitleErr = discord.Embed(title="Change title: Error",
                                description="Please select a maintitle or subtitle.",
                                colour=0x854bf7)
embTitleErr.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embTitleErr.set_footer(text="Made with expertise by HTOP")

embTimedOut = discord.Embed(title="Timed out!",
                                description="Sending file.",
                                colour=0x854bf7)
embTimedOut.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embTimedOut.set_footer(text="Made with expertise by HTOP")

embDone_G = discord.Embed(title="Success",
                        description=f"Please report any errors.",
                        colour=0x854bf7)
embDone_G.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
embDone_G.set_footer(text="Made with expertise by HTOP")

emb_conv_choice = discord.Embed(title="Converter: Choice",
                        description=f"Could not recognize the platform of the save, please choose what platform to convert the save to.",
                        colour=0x854bf7)
emb_conv_choice.set_thumbnail(url="https://cdn.discordapp.com/avatars/248104046924267531/743790a3f380feaf0b41dd8544255085.png?size=1024")
emb_conv_choice.set_footer(text="Made with expertise by HTOP")
