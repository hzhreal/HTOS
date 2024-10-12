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

| Second layer encryption game list        | PS4 -> PC conversion and vice versa | Quick cheats             | Extra re-region support (more than keystone & title id swapping) |
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
| Resident Evil Revelations 2              |                                     |                          |                                     |
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
- Give the bot permsisions to manage threads and delete messages in addition to the message content intents.

## Tutorial
Make sure to read everything.

### NPSSO
For the bot to completely function you need to input your NPSSO 64 character token. This is so you can be authorized to use the PSN API to obtain account ID from username.

How to obtain NPPSO:

- Go to playstation.com and login
- Go to this link https://ca.account.sony.com/api/v1/ssocookie
- Find `{"npsso":"<64 character npsso code>"}`
- If you leave it to "None" the psn.flipscreen.games website will be used to obtain account ID

### Everything else
- Download the pkg from https://github.com/hzhreal/cecie.nim/releases/tag/v3.00 and install it on your PS4
- Download the config.ini file from https://github.com/hzhreal/cecie.nim/blob/main/examples/config.ini and edit it with your desired 
  socket port and upload folder (path on PS4)
- Upload the config.ini file to `/data/cecie` on your PS4.
- Set up a Google Drive Service Account and grab the json file with the key 
  https://support.google.com/a/answer/7378726?hl=en (its free), if the json file has the key "universal_domain", you can remove it, in the case of an error
- Download the code from the bot and open the `.env` file, edit it as follows:  
  ```IP```: PS4 IP address  
  ```FTP_PORT```: The port that your FTP payload uses  
  ```CECIE_PORT```: The port that you used in the config.ini file  
  ```UPLOAD_PATH```: The path that you used in the config.ini file  
  ```MOUNT_PATH```: The path on your PS4 where the saves will be mounted  
  ```GOOGLE_DRIVE_JSON_PATH```: The path to the Google Drive Service Account json file  
  ```STORED_SAVES_FOLDER_PATH```: The path to the folder where you store saves for use in the quickresign command, format inside the folder is ```{NAME OF GAME}/{CUSAXXXXX}/{ANY NAME FOR SAVE}/{THE .BIN AND FILE}```  
  ```TOKEN```: Discord bot token  
  ```NPSSO```: The NPSSO token  
- Cd into the directory and run `pip install -r requirements.txt`
- Run bot.py
- Run the `/init` command in the channel you want the private threads to get created in, the button will work even if you restart the bot because it is a persistent view
- Make sure you are running the pkg
- Enjoy!
  
### Disclaimers
- Remember to not have the same folder for mount and upload. Have them in different paths, for example `/data/example/mount` & 
  `/data/example/upload`, these paths will get deleted and remade so you should not store anything there
- Saves created using this application will work on SaveWizard as long as you copy it from your PS4
- Make sure to use the latest cecie.nim release

### No jailbroken PS4?
- Join my discord where the bot is hosted, free to use and often hosted
  https://discord.gg/fHfmjaCXtb

## Credits
- https://github.com/Team-Alua/cecie.nim for creating the homebrew app that makes this possible, in addition to helping me
- https://github.com/dylanbbk & https://github.com/iCrazeiOS for help
- https://github.com/bucanero/save-decrypters for the extra encryption methods
- https://github.com/bucanero/pfd_sfo_tools/blob/master/sfopatcher/src/sfo.c for the param.sfo parser
- https://github.com/bucanero/apollo-lib/blob/main/source/patches.c#L2781 for the quick codes implementation
- https://github.com/Zhaxxy/rdr2_enc_dec/blob/main/rdr2_enc_dec.py for the checksum
- https://github.com/Zhaxxy/xenoverse2_ps4_decrypt for Xenoverse 2 extra layer of encryption
- https://github.com/monkeyman192/MBINCompiler/releases/tag/v5.02.0-pre2 for No Man's Sky obfuscation (mapping.json)
