# Usage
This is mostly for the bot, but some concepts are the same for the app.  
The bot only takes files, no zips or any other archives.  

## Threads
Click the create thread button in the channel that the bot is in. You will get mentioned in the created thread. All commands can be done there.
Only commands like `ping` or commands that only the bot owner can do, can be done outside threads.

## Uploads
When you are prompted to upload a save pair, what is meant is that you need to supply an encrypted save.
What makes an encrypted save is a file and a `.bin` file corresponding to it.  
An encrypted save is like an archive that keeps the gamesave and metadata inside.  

![image](https://github.com/hzhreal/HTOS/assets/142254293/19c7a4f6-1838-4bcf-872c-f087c0c5a9be)
Example of a save pair, `SAVEDATASGTA50000` & `SAVEDATASGTA50000.bin`.  

![image](https://github.com/hzhreal/HTOS/assets/142254293/b8273c63-7292-4d7a-9596-e6b6e69ad8bb)
Example of the save pair above decrypted.  

![image](https://github.com/hzhreal/HTOS/assets/142254293/2ed0b6b8-b18c-4a2b-94e9-5abb0b029043)
Example of an account ID, found inside a save exported from PS4. File structure is `PS4/SAVEDATA/{account ID}/{title ID}/{files}`.  

You supply these to the bot by dragging and dropping them through Discord, or by sending a public Google Drive folder link.
The bot can recursively search for save pairs from a Google Drive folder.  

## Bulk uploads
All save pair commands accept saves in bulk, except for when you upload a save from your region when re-regioning
(you can upload in bulk when you upload the ones you want to resign and re-region).
The quick codes command and convert command also accepts multiple savegames.  

## Database
When you give your username or account ID, it will get stored locally along with the associated Discord user ID for easy access.
This way, there is no need for entering the same values.  
When a thread is created, the thread ID is stored locally. Most commands you can only do in these valid threads.  
There is also a local database for blacklisted Discord user IDs and Playstation account IDs. Using the bot with these values is impossible.  

## Commands
* [Common arguments](#common-arguments)
* [User commands](#user-commands)
* [Bot owner commands](#bot-owner-commands)

### Common arguments
`playstation_id`: YOUR PLAYSTATION NETWORK USERNAME  
It will get converted to your account ID using the PSN API.  
If it fails you will get prompted to write in your account ID, you can find it in the folders by looking into the folders of a savefile from your account.  
Your account ID will be saved and you do not need to include the argument if you want to use the previously stored one.  

`shared_gd_link`: A link to your shared Google Drive folder.  
Make sure to set write permission for everyone. Only if you want the bot to upload the file to your shared drive, this is optional.  
The bot will still own the file, so it will get deleted in the future.  

### User commands

`/resign`: Accepts save pairs that will get resigned to your account ID, so you can use them on your account.  

---

`/decrypt`: Accept save pairs that will get decrypted so you can obtain the files inside it.   
If the game has second layer of encryption that is implemented, you will get prompted if you want it removed or not.  

**Arguments**:  
`include_sce_sys`: If you want to include the `sce_sys` folder that contains metadata about the save. Defaults to `False`.  
`secondlayer_choice`: Apply or do not apply second layer implementation for all saves applicable. If not included, then you will be prompted for each savepair applicable.  

---

`/encrypt`: Accepts save pairs that will get resigned, and you will get prompted to replace the files inside the save.  

**Arguments**:  
`upload_individually`: Choose if you want to upload the decrypted files one by one, or the ones you want at once.  
If you put it to `False`, and there is more than 1 file inside, you may have to rename the files you want uploaded using a format if you are using Discord upload.
The bot will prompt you on the details either way.  
`include_sce_sys`: Choose if you want to upload the contents of the 'sce_sys' folder. You can replace any sce_sys files you want, make sure to have the same filenames.
Defaults to `False`.  
`ignore_secondlayer_checks`: Choose if you want the bot to neglect checking if the files inside your save has a second layer implementation. Defaults to `False`.  
If the game has second layer of encryption that is implemented, the savefiles you swap will automatically get encrypted if needed.  

---

`/reregion`: First accepts a save pair from your region (upload 1 save pair only),
then obtains the keystone file and prompts you to upload the files you want to resign and re-region.  

---

`/createsave`: Create a save from scratch, will resign aswell. Follow instructions by bot on how to upload the files to put inside the save.  

**Arguments**:  
`savename`: The name you want to give the save.  
`saveblocks`: The size of the save in saveblocks (the size in bytes will be saveblocks * 2¹⁵).  
`savesize_mb`: The size of the save in MB.  
`ignore_secondlayer_checks`: Choose if you want the bot to neglect checking if the files inside your save has a second layer implementation. Defaults to `False`.  
Both `saveblocks` and `savesize_mb` represent the same concept, you must choose at least one of them. Keep in mind that `saveblocks` has priority over `savesize_mb`.  

---

`/convert`: Accepts a savegame that is decrypted (second layer of encryption can be present). The savefile will be converted from PS4 to PC or vice versa.   
The platform will get automatically detected, if not you will be prompted.  
**If your game is not available**:  
**PS4 -> PC**: Try to decrypt the PS4 save and use the decrypted file on PC.  
**PC -> PS4**: Try to encrypt the PC savefile into a PS4 save pair.    

**Arguments**:  
`game`: Game of the savefile.  
`savefile`: The savegame.  

---

`/store_accountid`: Store your account ID in the database. Use this if obtaining your account ID with username does not work.

**Arguments**:
`account_id`: Your account ID in hexadecimal format, the `0x` prefix is optional.

---

`/change picture`: Accepts a save pair that will get resigned and the save picture will get swapped.  

**Arguments**:  
`picture`: Image file that you want to use.  

---

`/change title`: Accepts a save pair that will get resigned, and the titles of the save will be swapped.  

**Arguments**:  
`maintitle`: For example `Grand Theft Auto V`.  
`subtitle`: For example `Franklin and Lamar (1.6%)`.  
These are changed in the param.sfo file.  

---

`/quick resign`: Brings up a list with stored saves by the hoster, you can choose which one you want resigned.
You will be prompted on which numbers to type in chat to choose save.  

---

`/quick cheats`: Accepts a savegame that you can add quick cheats to (second layer of encryption can be present).
The bot will prompt you with a UI that you can use to add whatever cheats that is available.  

**Arguments**:  
`game`: Game of the savefile.  
`savefile`. The savegame.  

---

`/quick codes`: Accepts savegames that you can apply Save Wizard quick codes to (must be fully decrypted).  
The save you input must be fully decrypted, then you can encrypt the resulting file into an encrypted save with the bot.  
However if there is a type of second layer that is not implemented in the bot, it will not work.  

**Arguments**:  
`codes`: The Save Wizard quick codes you want to apply.  

---

`/sfo read`: Accepts a param.sfo file, the metadata it contains will be shown.  

**Arguments**:  
`sfo`: The `param.sfo` file.  

---

`/sfo write`: Accepts a param.sfo file, you can patch the keys it contains  

**Arguments**:  
`sfo`: The `param.sfo` file.  
The rest of the arguments are keys in the param.sfo file that you can choose to patch.  

---

`/sealed_key decrypt`: Accepts a .bin file that you can find in a save pair. It will return the secret key it contains.  

**Argument**:  
`sealed_key`: The `.bin` file.  

---

`/info keyset`: Display the max the maximum keyset the hoster's console can mount/unmount and the firmware version associated.   

---

`/ping`: Check if the bot is functional!  

### Bot owner commands

`/init`: Set up the bot panel to create threads in the current channel.  

---

`/clear_threads`: Delete all threads created by the bot.  

---

`/blacklist add`: Add someone to the blacklist.  

**Arguments**:  
`ps_accountid`: PlayStation account ID in hexadecimal format.  
`user`: Discord user.  
Minimum 1 argument must be specified. 

---

`/blacklist remove`: Remove someone from the blacklist.  

**Arguments**:  
`ps_accountid`: PlayStation account ID in hexadecimal format.  
`user`: Discord user.  
Minimum 1 argument must be specified.  

---

`/blacklist remove_all`: Clear the blacklist.  

---

`/blacklist show`: Receive a JSON file of all the entries.  

## Other guides
* [Kidd's Nexus](https://www.youtube.com/@kiddsnexus): [HTOS Tutorials](https://www.youtube.com/playlist?list=PLxevmZH4AJusnb9VnOpRojfe8fQndy1Js)
* [That-Kidd](https://github.com/That-Kidd): [HTOS Tutorials](https://github.com/That-Kidd/ps-resources/tree/main/HTOS)
