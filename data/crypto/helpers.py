import discord
from discord.ui.item import Item
from types import SimpleNamespace

from data.crypto import CryptoError
from utils.helpers import DiscordContext, TimeoutHelper
from utils.constants import (
    logger, OTHER_TIMEOUT,
    GTAV_TITLEID, BL3_TITLEID, RDR2_TITLEID, XENO2_TITLEID, WONDERLANDS_TITLEID, NDOG_TITLEID, NDOG_COL_TITLEID, NDOG_TLOU2_TITLEID, 
    MGSV_TPP_TITLEID, MGSV_GZ_TITLEID, REV2_TITLEID, RE7_TITLEID, RERES_TITLEID, DL1_TITLEID, DL2_TITLEID, RGG_TITLEID, DI1_TITLEID, DI2_TITLEID, NMS_TITLEID,
    TERRARIA_TITLEID, SMT5_TITLEID, RCUBE_TITLEID, DSR_TITLEID, RE4R_TITLEID
)
from utils.embeds import embdecTimeout, embdecFormat, embErrdec

async def extra_decrypt(d_ctx: DiscordContext | None, Crypto: SimpleNamespace, title_id: str, destination_directory: str, savePairName: str) -> None:
    helper = TimeoutHelper(embdecTimeout)
    emb = embdecFormat.copy()
    emb.title = emb.title.format(savename=savePairName)

    class CryptChoiceButton(discord.ui.View):
        def __init__(self, game: str | None = None, start_offset: int | None = None, title_id: str | None = None) -> None:
            self.game = game
            self.offset = start_offset
            self.title_id = title_id
            super().__init__(timeout=OTHER_TIMEOUT)
                
        async def on_timeout(self) -> None:
            self.disable_all_items()
            await helper.handle_timeout(d_ctx.msg)

        async def on_error(self, error: Exception, _: Item, __: discord.Interaction) -> None:
            self.disable_all_items()
            emb = embErrdec.copy()
            emb.description = emb.description.format(error=error)
            helper.embTimeout = emb
            await helper.handle_timeout(d_ctx.msg)
            logger.exception(f"{error} - {d_ctx.ctx.user.name}")
            
        @discord.ui.button(label="Decrypted", style=discord.ButtonStyle.blurple, custom_id="decrypt")
        async def decryption_callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(view=None)
            try:
                match self.game:
                    case "GTAV" | "RDR2":
                        await Crypto.Rstar.decryptFile(destination_directory, self.offset)
                    case "XENO2":
                        await Crypto.Xeno2.decryptFile(destination_directory)
                    case "BL3":
                        await Crypto.BL3.decryptFile(destination_directory, "ps4", False)
                    case "TTWL":
                        await Crypto.BL3.decryptFile(destination_directory, "ps4", True)
                    case "NDOG":
                        await Crypto.Ndog.decryptFile(destination_directory, self.offset)
                    case "MGSV":
                        await Crypto.MGSV.decryptFile(destination_directory, self.title_id)
                    case "REV2":
                        await Crypto.Rev2.decryptFile(destination_directory)
                    case "DL1" | "DL2" | "DI1":
                        await Crypto.DL.decryptFile(destination_directory)
                    case "RGG":
                       await Crypto.RGG.decryptFile(destination_directory)
                    case "DI2":
                        await Crypto.DI2.decryptFile(destination_directory)
                    case "NMS":
                        await Crypto.NMS.decryptFile(destination_directory)
                    case "TERRARIA":
                        await Crypto.TERRARIA.decryptFile(destination_directory)
                    case "SMT5":
                        await Crypto.SMT5.decryptFile(destination_directory)
                    case "RCUBE":
                        await Crypto.RCube.decryptFile(destination_directory)
                    case "DSR":
                        await Crypto.DSR.decryptFile(destination_directory)
                    case "RE4R":
                        await Crypto.RE4R.decryptFile(destination_directory)
            except (ValueError, IOError, IndexError):
                raise CryptoError("Invalid save!")
            
            helper.done = True
            
        @discord.ui.button(label="Encrypted", style=discord.ButtonStyle.blurple, custom_id="encrypt")
        async def encryption_callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(view=None)
            helper.done = True

    if title_id in GTAV_TITLEID:
        if not d_ctx:
            await Crypto.Rstar.decryptFile(destination_directory, Crypto.Rstar.GTAV_PS_HEADER_OFFSET)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("GTAV", start_offset=Crypto.Rstar.GTAV_PS_HEADER_OFFSET))
        await helper.await_done()
        
    elif title_id in RDR2_TITLEID:
        if d_ctx:
            await Crypto.Rstar.decryptFile(destination_directory, Crypto.Rstar.RDR2_PS_HEADER_OFFSET)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("RDR2", start_offset=Crypto.Rstar.RDR2_PS_HEADER_OFFSET))
        await helper.await_done()

    elif title_id in XENO2_TITLEID:
        if not d_ctx:
            await Crypto.Xeno2.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("XENO2"))
        await helper.await_done()

    elif title_id in BL3_TITLEID:
        if not d_ctx:
            await Crypto.BL3.decryptFile(destination_directory, "ps4", False)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("BL3"))
        await helper.await_done()

    elif title_id in WONDERLANDS_TITLEID:
        if not d_ctx:
            await Crypto.BL3.decryptFile(destination_directory, "ps4", True)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("TTWL"))
        await helper.await_done()

    elif title_id in NDOG_TITLEID:
        if not d_ctx:
            await Crypto.Ndog.decryptFile(destination_directory, Crypto.Ndog.START_OFFSET)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET))
        await helper.await_done()

    elif title_id in NDOG_COL_TITLEID:
        if not d_ctx:
            await Crypto.Ndog.decryptFile(destination_directory, Crypto.Ndog.START_OFFSET_COL)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET_COL))
        await helper.await_done()

    elif title_id in NDOG_TLOU2_TITLEID:
        if not d_ctx:
            await Crypto.Ndog.decryptFile(destination_directory, Crypto.Ndog.START_OFFSET_TLOU2)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET_TLOU2))
        await helper.await_done()

    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
        if not d_ctx:
            await Crypto.MGSV.decryptFile(destination_directory, title_id)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("MGSV", title_id=title_id))
        await helper.await_done()

    elif title_id in REV2_TITLEID:
        if not d_ctx:
            await Crypto.Rev2.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("REV2"))
        await helper.await_done()

    elif title_id in DL1_TITLEID:
        if not d_ctx:
            await Crypto.DL.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("DL1"))
        await helper.await_done()

    elif title_id in DL2_TITLEID:
        if not d_ctx:
            await Crypto.DL.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("DL2"))
        await helper.await_done()
    
    elif title_id in RGG_TITLEID:
        if not d_ctx:
            await Crypto.RGG.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("RGG"))
        await helper.await_done()

    elif title_id in DI1_TITLEID:
        if not d_ctx:
            await Crypto.DL.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("DI1"))
        await helper.await_done()

    elif title_id in DI2_TITLEID:
        if not d_ctx:
            await Crypto.DI2.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("DI2"))
        await helper.await_done()

    elif title_id in NMS_TITLEID:
        if not d_ctx:
            await Crypto.NMS.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("NMS"))
        await helper.await_done()
    
    elif title_id in TERRARIA_TITLEID:
        if not d_ctx:
            await Crypto.TERRARIA.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("TERRARIA"))
        await helper.await_done()
    
    elif title_id in SMT5_TITLEID:
        if not d_ctx:
            await Crypto.SMT5.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("SMT5"))
        await helper.await_done()
    
    elif title_id in RCUBE_TITLEID:
        if not d_ctx:
            await Crypto.RCube.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("RCUBE"))
        await helper.await_done()

    elif title_id in DSR_TITLEID:
        if not d_ctx:
            await Crypto.DSR.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("DSR"))
        await helper.await_done()

    elif title_id in RE4R_TITLEID:
        if not d_ctx:
            await Crypto.RE4R.decryptFile(destination_directory)
            return

        await d_ctx.msg.edit(embed=emb, view=CryptChoiceButton("RE4R"))
        await helper.await_done()

async def extra_import(Crypto: SimpleNamespace, title_id: str, file_name: str) -> None:
    try:
        if title_id in GTAV_TITLEID:
            await Crypto.Rstar.checkEnc_ps(file_name, GTAV_TITLEID)
           
        elif title_id in RDR2_TITLEID:
            await Crypto.Rstar.checkEnc_ps(file_name, RDR2_TITLEID)
            
        elif title_id in XENO2_TITLEID:
            await Crypto.Xeno2.checkEnc_ps(file_name)

        elif title_id in BL3_TITLEID:
            await Crypto.BL3.checkEnc_ps(file_name, False)
        
        elif title_id in WONDERLANDS_TITLEID:
            await Crypto.BL3.checkEnc_ps(file_name, True)

        elif title_id in NDOG_TITLEID:
            await Crypto.Ndog.checkEnc_ps(file_name, Crypto.Ndog.START_OFFSET)

        elif title_id in NDOG_COL_TITLEID:
            await Crypto.Ndog.checkEnc_ps(file_name, Crypto.Ndog.START_OFFSET_COL)

        elif title_id in NDOG_TLOU2_TITLEID:
            await Crypto.Ndog.checkEnc_ps(file_name, Crypto.Ndog.START_OFFSET_TLOU2)

        elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
            await Crypto.MGSV.checkEnc_ps(file_name, title_id)

        elif title_id in REV2_TITLEID:
            await Crypto.Rev2.checkEnc_ps(file_name)

        elif title_id in RE7_TITLEID or title_id in RERES_TITLEID:
            await Crypto.RE7.checkEnc_ps(file_name)

        elif title_id in DL1_TITLEID:
            await Crypto.DL.checkEnc_ps(file_name, "DL1")

        elif title_id in DL2_TITLEID:
            await Crypto.DL.checkEnc_ps(file_name, "DL2")

        elif title_id in RGG_TITLEID:
            await Crypto.RGG.checkEnc_ps(file_name)

        elif title_id in DI1_TITLEID:
            await Crypto.DL.checkEnc_ps(file_name, "DI1")
        
        elif title_id in DI2_TITLEID:
            await Crypto.DI2.checkEnc_ps(file_name)

        elif title_id in NMS_TITLEID:
            await Crypto.NMS.checkEnc_ps(file_name)
        
        elif title_id in TERRARIA_TITLEID:
            await Crypto.TERRARIA.checkEnc_ps(file_name)
        
        elif title_id in SMT5_TITLEID:
            await Crypto.SMT5.checkEnc_ps(file_name)
        
        elif title_id in RCUBE_TITLEID:
            await Crypto.RCube.checkEnc_ps(file_name)

        elif title_id in DSR_TITLEID:
            await Crypto.DSR.checkEnc_ps(file_name)

        elif title_id in RE4R_TITLEID:
            await Crypto.RE4R.checkEnc_ps(file_name)

    except CryptoError as e:
        raise CryptoError(e)
    except (ValueError, IOError, IndexError):
        raise CryptoError("Invalid save!")