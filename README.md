# HTOS
A discord bot with tons of functionalities that can handle PS4 saves using a jailbroken PS4.

## Purposes
- Resign encrypted saves (both with or without replacing the decrypted contents, also known as encrypting)
- Decrypt encrypted saves
- Re-region encrypted saves
- Change the picture of encrypted saves
- Change the titles of encrypted saves
- Quickly resign pre stored saves
- Convert gamesaves from PS4 to PC or vice versa (some games require extra conversion, those implemented are in table below) 
- Add quick cheats to your games (available games are in table below)
- Apply save wizard quick codes to your saves
- Create saves from scratch

## Functionalities
- File uploads through discord and google drive (bulk uploads are supported on all save pair commands)
- File security checks
- Game custom cryptography handling (extra encryption layer based on game, in table below)
- Param.sfo parser
- Asynchronous, can handle multiple operations at once
- Bot will guide you with what do to in each command
- All commands except ping will only work in private threads created by the bot, thread IDs are stored in .db file
- Everything will get cleaned up locally and on the PS4
- All commands that takes save pairs will resign
- Account ID database, do not include playstation_id parameter if you want to use previously stored account ID
- Interactive user interface

| Extra security/layers supported game list| PS4 -> PC conversion and vice versa | Quick cheats             | Extra re-region support (more than keystone & title id swapping) |
| ---------------------------------------- | ----------------------------------- | ------------------------ | ---------------------------------------------------------------- |
| Borderlands 3                            | Borderlands 3                       |                          |                                     |
| Dead Island 1 (compression only)         |                                     |                          |                                     |
| Dead Island 2 (compression only)         |                                     |                          |                                     |
| Dying Light 1 (compression only)         |                                     |                          |                                     |
| Dying Light 2 (compression only)         |                                     |                          |                                     |
| Grand Theft Auto V                       | Grand Theft Auto V                  | Grand Theft Auto V       |                                     |
| Like a Dragon: Ishin                     |                                     |                          |                                     |
| Metal Gear Solid V: Ground Zeroes        |                                     |                          | Metal Gear Solid V: Ground Zeroes   |
| Metal Gear Solid V: The Phantom Pain     |                                     |                          | Metal Gear Solid V: The Phantom Pain|
| No Man's Sky (savedata.hg)               |                                     |                          |                                     |
| Raspberry Cube                           |                                     |                          |                                     |
| Red Dead Redemption 2                    | Red Dead Redemption 2               | Red Dead Redemption 2    |                                     |
| Resident Evil: Resistance                |                                     |                          |                                     |
| Resident Evil: Revelations 2             |                                     |                          |                                     |
| Resident Evil 7: Biohazard               |                                     |                          |                                     |
| Shin Megami Tensei 5                     |                                     |                          |                                     |
| Terraria (.plr & some .wld)              |                                     |                          |                                     |
| The Last of Us                           |                                     |                          |                                     |
| The Last of Us Part II                   |                                     |                          |                                     |
| Tiny Tina's Wonderlands                  | Tiny Tina's Wonderlands             |                          |                                     |
| Uncharted 4                              |                                     |                          |                                     |
| Uncharted: The Lost Legacy               |                                     |                          |                                     |
| Uncharted: The Nathan Drake Collection   |                                     |                          |                                     |
| Xenoverse 2                              |                                     |                          | Xenoverse 2                         |

If you wanna contribute to this list, please let me know!

## Requirements
- A jailbroken PS4 running atleast GoldHEN v2.4b14 payload
- Give the bot permsisions to manage threads and delete messages in addition to the message content intents  

## Tutorial
Make sure to read everything.

### NPSSO
For the bot to completely function you need to input your NPSSO 64 character token. This is so you can be authorized to use the PSN API to obtain account ID from username. Make sure to read more about it [here](https://github.com/isFakeAccount/psnawp/blob/master/README.md#getting-started) where you can find out how to obtain it. If you choose not to, then psn.flipscreen.games will be used.  

### Everything else
- Download the [pkg](https://github.com/hzhreal/cecie.nim/releases/latest) from and install it on your PS4
- Download the [config.ini](https://github.com/hzhreal/cecie.nim/blob/main/examples/config.ini) file from and edit it with your desired 
  socket port and upload folder (path on PS4)
- Upload the `config.ini` file to `/data/cecie` on your PS4  
- Set up a [Google Service Account](https://support.google.com/a/answer/7378726?hl=en) or a [Google OAuth Client](https://support.google.com/cloud/answer/15549257?hl=en), remember to enable the Drive API and to download the JSON credentials. New service accounts do not get storage, so you should setup an OAuth client instead.   
- Clone the repository and open the `.env` file, edit it as follows:  
  ```IP```: PS4 IP address  
  ```FTP_PORT```: The port that your FTP payload uses  
  ```CECIE_PORT```: The port that you used in the `config.ini` file  
  ```UPLOAD_PATH```: The path that you used in the `config.ini` file  
  ```MOUNT_PATH```: The path on your PS4 where the saves will be mounted  
  ```GOOGLE_DRIVE_JSON_PATH```: The path to the Google Drive credentials JSON file  
  ```STORED_SAVES_FOLDER_PATH```: The path to the folder where you store saves for use in the `quick resign` command, format inside the folder is ```{NAME OF GAME}/{CUSAXXXXX}/{ANY NAME FOR SAVE}/{THE .BIN(s) AND FILE(s)}```  
  ```TOKEN```: Discord bot token  
  ```NPSSO```: The NPSSO token  
- Run `pip install -r requirements.txt` inside the directory where the bot is located to install the necessary packages
- Execute `bot.py` using Python
- Run the `/init` command in the channel you want the private threads to get created in, you will only need to do this once in each server  
- Make sure the pkg is running when the bot is
- Enjoy!
  
### Disclaimers
- Remember to not have the same folder for mount and upload. Have them in different paths, for example `/data/example/mount` & 
  `/data/example/upload`, these paths will get wiped and remade, so you should not store anything there
- Saves created using this application will work on SaveWizard as long as you copy it from your PS4
- Make sure to use the latest `cecie.nim` release

### No jailbroken PS4?
- Join my [Discord](https://discord.gg/fHfmjaCXtb) where the bot is hosted, free to use and often hosted

### Acknowledgements
- [Batang](https://github.com/B-a-t-a-n-g)
- [Bucanero](https://github.com/bucanero): [apollo-lib](https://github.com/bucanero/apollo-lib)
- [Bucanero](https://github.com/bucanero): [pfd_sfo_tools](https://github.com/bucanero/pfd_sfo_tools)
- [Bucanero](https://github.com/bucanero): [save-decrypters](https://github.com/bucanero/save-decrypters)
- [DylanBBK](https://github.com/dylanbbk)
- [iCraze](https://github.com/iCrazeiOS)
- [monkeyman192](https://github.com/monkeyman192): [MBINCompiler](https://github.com/monkeyman192/MBINCompiler)
- [Team-Alua](https://github.com/Team-Alua): [Cecie](https://github.com/Team-Alua/cecie.nim)
- [Zhaxxy](https://github.com/Zhaxxy): [rdr2_enc_dec](https://github.com/Zhaxxy/rdr2_enc_dec)
- [Zhaxxy](https://github.com/Zhaxxy): [xenoverse2_ps4_decrypt](https://github.com/Zhaxxy/xenoverse2_ps4_decrypt)
