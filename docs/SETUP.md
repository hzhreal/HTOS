# Setup
The setup process is split into minimal and full setup.  
If you only want to set up the app, then you only need to do the minimal part.  
If you want to set up the bot, then you need to do both.  

## Prerequisites
* A jailbroken PS4 running at least GoldHEN v2.4b14.

## Minimal setup
Start off by downloading and installing the [cecie](https://github.com/hzhreal/cecie.nim/releases/latest) package file on to your PS4.  

Then download the [config.ini](https://github.com/hzhreal/cecie.nim/blob/main/examples/config.ini) file and start editing it. You should not use any whitespaces in this file.  
`saveDirectory`: This is the folder where encrypted saves will be uploaded and deleted afterwards. You can for example set this to `/data/htos/upload`.  
`port`: Let this be any available port on your console, if you are unsure, just leave it as default.  
After editing, upload the `config.ini` file to the `/data/cecie` folder on your console. If the directory does not already exist, you will need to create it yourself.  

In the root directory of the repository, find the `.env` file and start editing it. You can use whitespaces in this file.  
`IP`: The IP address of the console.  
`FTP_PORT`: The FTP port you use to connect to the console using FTP, usually `2121`.  
`CECIE_PORT`: Set this to the same number as `port` from the `config.ini` file.  
`UPLOAD_PATH`: Set this to the same path as `saveDirectory` from the `config.ini` file.  
`MOUNT_PATH`: This is the folder where decrypted files will be temporarily stored. This should not be the same as `UPLOAD_PATH`.
You can for example set this to `/data/htos/mount`.  

The usual way to start the app should be by first running the `cecie` homebrew application on your console.
Then in the root directory of the repository you should, run with [uv](https://docs.astral.sh/uv/getting-started/installation/)
```
uv run app.py
```
or any equivalent command (dependencies must be installed, with uv this is done automatically).  
On startup of the program, the folders you set as `UPLOAD_PATH` and `MOUNT_PATH` will be deleted and remade. They will also be cleaned after any operation is finished.  
The directories `UPLOAD_PATH` and `MOUNT_PATH` must exist when the program is running. Either create them manually or have the FTP server running before you run the program.  
The application stores files temporarily in the `UserSaves` folder from where you run the application from. The startup process also makes sure these folders are made.  
To run without the start up process, add the flag `--ignore-startup`. You may want to do this if your console is not on yet because it will try to make a FTP connection and timeout.  

Logs are written to files inside the `logs` folder from where you run the application from.  

## Full setup

For the bot to completely function you need to input your NPSSO 64 character token. This is so you can be authorized to use the PSN API to obtain account ID from username.  
Make sure to read more about it [here](https://github.com/isFakeAccount/psnawp/blob/master/README.md#getting-started) where you can find out how to obtain it.  
> [!TIP]
> Although it is recommended that you do this step, the bot can function without.
> But then, account ID must be manually set using the `store_accountid` command and will not be converted from username.
> Once username or account ID is given, it is saved for that Discord user and if no value is given in a command, then it will default to the saved one.

Now you need to set up a [Google OAuth Client](https://support.google.com/cloud/answer/15549257?hl=en). You should follow the tutorial in the link.  
The bot will accept files from Google Drive and will upload the final files there, if the Discord filesize limit is exceeded.  
Some things to keep in mind are
* When you are prompted to select application type, select `Desktop app`.
* Add the email of the Google Drive account you want to use as a tester.
* On the Google Cloud dashboard, make sure to enable the Google Drive API.  
A [Google Service Account](https://support.google.com/a/answer/7378726?hl=en) is also supported. But after April 15, 2025, new service accounts do not get any storage.  
Therefore, new service accounts will not work.  

Now, go back to editing the `.env` file.  
`STORED_SAVES_FOLDER_PATH`: This is the folder where pre-existing saves are stored for use in the `quick resign` command.  
The format inside this folder is 
```{NAME OF GAME}/{CUSAXXXXX}/{ANY NAME FOR SAVE}/{THE .BIN(s) AND FILE(s)}```.
So for example, you can create the path `"Grand Theft Auto V/CUSA00411/Max money"` and store one or multiple encrypted save pairs inside.  
`GOOGLE_DRIVE_JSON_PATH`: Set this to the path to the Google OAuth Client credentials JSON file, or the Google Service Account JSON credentials file.  
`NPSSO`: The 64 character token that will be used for obtaining account ID from a username.  
`TOKEN`: The Discord bot token.  
The bot needs
* Permission `Manage Threads and Posts`.
* Intent `Message Content`.

You run the bot the same way as you would do the app.  
The only difference is that you run `bot.py`,
```
uv run bot.py
```
or any equivalent command.  
The `--ignore-startup` flag is also available. The only extra step in the startup process for the bot is making sure the database files exist, and in the correct format.  

Do the `/init` command in the channel where you want the threads to get created in. You only need to do this once.  
