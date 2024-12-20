# Quick tutorial for the end user
The bot only takes files, no zips or any other compression like that.

## Threads
Click the create thread button in the channel that the bot's message is in, thereafter enter the thread you receive. You can do the commands there.

## Uploads
When you do a command that takes save pairs (encrypted saves which is a file and .bin corresponding to it), you can upload it straight through discord or send a public google drive folder link.

## Bulk uploads
All save pair commands accept saves in bulk, except for when you upload a save from your region when re-regioning (you can upload in bulk when you upload the ones you want to resign and re-region. Quick code command also accepts multiple savegames.

## Commands
**common parameter**: playstation_id, YOUR PLAYSTATION NETWORK USERNAME  
It will get converted to your account ID using the psn api. 

If it fails you will get prompted to write in your accound ID, you can find it in the folders by looking into the folders of a savefile from your account. 

Your account ID will be saved and you do not need to include the parameter if you want to use the previously stored one.

# List of commands

**resign**: Accepts save pairs that will get resigned to your account ID, so you can use them on your account.  

//

**decrypt**: Accept save pairs that will get decrypted so you can obtain the files inside it.   
**Parameter**: include_sce_sys, this is just if you want the system files of the save   
If the game has second layer of encryption that is implemented, you will get prompted if you want it removed or not.  

//

**encrypt**: Accepts save pairs that will get resigned, and you will get prompted to replace the files inside the save.  
**Parameters**:
- upload_individually, Choose if you want to upload the decrypted files one by one, or the ones you want at once. Put to true if you want to swap all the files in the save. If you put it to false, and there is more than 1 file inside, you will have to rename the files you want uploaded using a format. The bot will prompt you on the details.
- include_sce_sys, Choose if you want to upload the contents of the 'sce_sys' folder. You can replace any sce_sys files you want, make sure to have the same filenames. 
- ignore_secondlayer_checks, Choose if you want the bot to neglect checking if the files inside your save can be encrypted/compressed.  
If the game has second layer of encryption that is implemented, the savefiles you swap will automatically get encrypted if needed.  

//

**reregion**: First accepts a save pair from your region (upload 1 save pair only), then obtains the keystone file and prompts you to upload the files you want to resign and re-region.  

//

**change picture**: Accepts a save pair that will get resigned and the save png will get swapped.  
**Parameter**: picture, this is the file you want to swap the picture with  

//

**quick resign**: Brings up a list with stored saves by the hoster, you can choose which one you want resigned. You will be prompted on which numbers to type in chat to choose save.  

//

**change title**: Accepts a save pair that will get resigned, and the titles of the save will be swapped.  
**Parameters**: 
- maintitle, for example Grand Theft Auto V
- subtitle, for example Franklin and Lamar (1.6%)
These are changed in the param.sfo file.  

//

**convert**: Accepts a savegame that is decrypted (second layer of encryption can be present). The savefile will be converted from PS4 to PC or vice versa.   
**Parameters**:
- game, select the game of the savefile
- savefile, the file itself
The platform will get automatically detected, if not you will be prompted.  
**If your game is not available**:  
**PS4 -> PC**: Try to decrypt the PS4 save and use the decrypted file on PC.  
**PC -> PS4**: Try to encrypt the PC savefile into a PS4 save pair.    

//

**quick cheats**: Accepts a savegame that you can add quick cheats to (second layer of encryption can be present). The bot will prompt you with a UI that you can use to add whatever cheats that is available.   
**Parameters**
- game, select the game of the savefile
- savefile, the file itself   

//

**quick codes**: Accepts savegames that you can apply save wizard quick codes to (must be fully decrypted).  
**Parameters**
- codes, the save wizard quick codes
- endianness, try without this parameter first, if it does not work put it to big  
The save you input must be fully decrypted, then you can encrypt with the bot, however if there is a type of encryption/checksum that is not implemented in the bot it will not work.

//

**sfo read**: Accepts a param.sfo file, the data it contains will be shown.  
**Parameters**:
- sfo, the file itself

//

**sfo write**: Accepts a param.sfo file, you can patch the keys it contains  
**Parameters**:
- sfo, the file itself
- The rest of the parameters are keys in the param.sfo file that you can choose to patch

//

**sealed_key decrypt**: Accepts a .bin file that you can find in a save pair. It will return the secret key it contains.  
**Parameter**:
- sealed_key, the file itself

//

**createsave**: Create a save from scratch, will resign aswell. Follow instructions by bot on how to upload the files to put inside the save.
**Parameters**:  
- savename, the name you want to give the save  
- saveblocks, the size of the save (saveblocks * 2¹⁵) 
- ignore_secondlayer_checks, Choose if you want the bot to neglect checking if the files inside your save can be encrypted/compressed.  

//

**store_accountid**: Store your account ID in the database. Use this if obtaining your account ID with username does not work.
**Parameter**:
- account_id, your account ID in hexadecimal format

//

**info keyset**: Display the max the maximum keyset the hoster's console can mount/unmount and the firmware version associated

//

**init**: Bot owner command to set up the bot panel to create threads

//

**clear_threads**: Bot owner command to delete all threads created by the bot

//

**blacklist add**: Bot owner can blacklist someone
**Parameters**:
- ps_accountid, PlayStation account ID in hexadecimal format
- user, Discord user
Minimum 1 argument  

//

**blacklist remove**: Bot owner can remove someone from the blacklist
**Parameters**:
- ps_accountid, PlayStation account ID in hexadecimal format
- user, Discord user  
Minimum 1 argument  

//

**blacklist remove_all**: Bot owner can clear the blacklist

//

**blacklist show**: Bot owner can list all blacklisted entries

//

**ping**: Check if the bot is functional!  

## Examples
![image](https://github.com/hzhreal/HTOS/assets/142254293/19c7a4f6-1838-4bcf-872c-f087c0c5a9be)
Example of a save pair, "SAVEDATASGTA50000" & "SAVEDATASGTA50000.bin"

![image](https://github.com/hzhreal/HTOS/assets/142254293/b8273c63-7292-4d7a-9596-e6b6e69ad8bb)
Example of the save pair above decrypted.

![image](https://github.com/hzhreal/HTOS/assets/142254293/2ed0b6b8-b18c-4a2b-94e9-5abb0b029043)
Example of an account ID, found inside a save exported from PS4. File structure is: PS4/SAVEDATA/{account ID}/{title ID}/{files}

## Disclaimers
**IF YOU GET "The application did not respond" CHECK IF THE BOT IS EVEN ONLINE!**
Enjoy!
