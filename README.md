# HTOS
A Discord bot and app to manage external PS4 saves using a jailbroken PS4.

## Features
* Resign encrypted saves.
* Decrypt encrypted saves.
* Encrypt decrypted files into encrypted saves.
* Re-region encrypted saves.
* Change the picture of encrypted saves.
* Change the titles of encrypted saves.
* Quickly resign pre stored saves.
* Convert gamesaves from PS4 to PC or vice versa (some games require extra implementation, see table below).
* Add quick cheats to your games (available games are in table below).
* Apply save wizard quick codes to your saves.
* Create saves from scratch.
* Edit `param.sfo` files
* Library of games supported that need extra implementation (see table below).

## Table of games with extra implementation
Certain games need to have an extra implementation for it to work out of the box.  

| Game                                     | Second layer            | PS4 -> PC conversion and vice versa | Quick cheats             | Extra re-region support            |
| ---------------------------------------- | ----------------------- | ----------------------------------- | ------------------------ | -----------------------------------|
| Borderlands 3                            | :white_check_mark:      | :white_check_mark:                  | :black_circle:           | :white_circle:                     |
| Dark Souls: Remastered                   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Dead Island 1                            | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Dead Island 2                            | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Digimon World: Next Order                | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Dying Light 1                            | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Dying Light 2                            | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Grand Theft Auto V                       | :white_check_mark:      | :white_check_mark:                  | :large_blue_circle:      | :white_circle:                     |
| Like a Dragon: Ishin                     | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Metal Gear Solid V: Ground Zeroes        | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_check_mark:                 |
| Metal Gear Solid V: The Phantom Pain     | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_check_mark:                 |
| Minecraft: Legacy Edition                | :white_circle:          | :white_circle:                      | :black_circle:           | :white_check_mark:                 |
| Nioh 2                                   | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| No Man's Sky                             | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Raspberry Cube                           | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Red Dead Redemption 2                    | :white_check_mark:      | :white_check_mark:                  | :large_blue_circle:      | :white_circle:                     |
| Resident Evil 2 Remake                   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Resident Evil 3 Remake                   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Resident Evil 4 Remake                   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Resident Evil 7: Biohazard               | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Resident Evil: Resistance                | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Resident Evil: Revelations 2             | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Shin Megami Tensei 5                     | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Stardew Valley                           | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Terraria                                 | :large_blue_circle:     | :white_circle:                      | :black_circle:           | :white_circle:                     |
| The Last of Us                           | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| The Last of Us Part II                   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Tiny Tina's Wonderlands                  | :white_check_mark:      | :white_check_mark:                  | :black_circle:           | :white_circle:                     |
| Uncharted 2: Remastered                  | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Uncharted 3: Remastered                  | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Uncharted 4                              | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Uncharted: The Lost Legacy               | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Uncharted: The Nathan Drake Collection   | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_circle:                     |
| Xenoverse 2                              | :white_check_mark:      | :white_circle:                      | :black_circle:           | :white_check_mark:                 |

> [!NOTE]
> Resigning and re-regioning will mostly work with all games.
> Changing stuff like the save picture or save titles will always work because we are not modifying the savegame, only the metadata.
> So for every other game you can try and test if it will work out of the box.

If you wanna contributions to this list, you can create an issue with information, create a pull request, or contact me on Discord.  

### Explanation of unintuitive table headers
**Second layer**: The savegame can for example have some sort of encryption, compression, or checksum.  
When encrypting, decrypting, or adding quick codes to the save, you will need some sort of way to deal with this. For example using some other program.  
That is, if you want to make modifications to the savegame without corrupting it.  

### Explanation of unintuitive table cells
:white_check_mark:: Assumed to be fully implemented.  

:large_blue_circle:: Partially implemented:  
Dead Island 1: There may be unimplemented checksums.  
Dead Island 2: Unimplemented checksums.  
Dying Light 2: Unimplemented checksums.  
Grand Theft Auto V: Only money quick cheat is implemented.  
Nioh 2: Checksum fix is for version 01.27 only.  
No Man's Sky: Only `savedata.hg` is implemented.  
Red Dead Redemption 2: Only money quick cheat is implemented.  
Terraria: Only `.plr` and some `.wld` are implemented.  


:white_circle:: Assumed to not need an implementation, may or may not work.  

:black_circle:: Not implemented.  

## Setup
[SETUP.md](docs/SETUP.md)

## Usage
[USAGE.md](docs/USAGE.md)

## No jailbroken PS4?
* Join my [Discord](https://discord.gg/fHfmjaCXtb) where the bot is hosted, free to use and often hosted.

## Acknowledgements
* [Alfizari](https://github.com/alfizari)
* [Alfizari](https://github.com/alfizari): [Dark-Souls-Remastered-Save-decrypt-PS4](https://github.com/alfizari/Dark-Souls-Remastered-Save-decrypt-PS4)
* [AxrzZ](https://github.com/AxrzZ)
* [Batang](https://github.com/B-a-t-a-n-g)
* [Bawsdeep](https://github.com/bawsdeep): [xenoverse2_crypt_checksum](https://github.com/bawsdeep/xenoverse2_crypt_checksum)
* [Brotherguns5624](https://github.com/Brotherguns5624)
* [Bucanero](https://github.com/bucanero): [apollo-lib](https://github.com/bucanero/apollo-lib)
* [Bucanero](https://github.com/bucanero): [pfd_sfo_tools](https://github.com/bucanero/pfd_sfo_tools)
* [Bucanero](https://github.com/bucanero): [save-decrypters](https://github.com/bucanero/save-decrypters)
* [DylanBBK](https://github.com/dylanbbk)
* [iCraze](https://github.com/iCrazeiOS)
* [Monkeyman192](https://github.com/monkeyman192): [MBINCompiler](https://github.com/monkeyman192/MBINCompiler)
* [Team-Alua](https://github.com/Team-Alua): [Cecie](https://github.com/Team-Alua/cecie.nim)
* [That-Kidd](https://github.com/That-Kidd)
* [Zhaxxy](https://github.com/Zhaxxy): [rdr2_enc_dec](https://github.com/Zhaxxy/rdr2_enc_dec)
* [Zhaxxy](https://github.com/Zhaxxy): [xenoverse2_ps4_decrypt](https://github.com/Zhaxxy/xenoverse2_ps4_decrypt)
