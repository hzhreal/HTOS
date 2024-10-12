import discord
from discord.ui.item import Item
from types import SimpleNamespace
from data.crypto import CryptoError
from utils.helpers import DiscordContext, TimeoutHelper
from utils.constants import (
    logger, Color, Embed_t, OTHER_TIMEOUT,
    GTAV_TITLEID, BL3_TITLEID, RDR2_TITLEID, XENO2_TITLEID, WONDERLANDS_TITLEID, NDOG_TITLEID, NDOG_COL_TITLEID, NDOG_TLOU2_TITLEID, 
    MGSV_TPP_TITLEID, MGSV_GZ_TITLEID, REV2_TITLEID, DL1_TITLEID, DL2_TITLEID, RGG_TITLEID, DI1_TITLEID, DI2_TITLEID, NMS_TITLEID,
    TERRARIA_TITLEID, SMT5_TITLEID, RCUBE_TITLEID
)

async def extra_decrypt(d_ctx: DiscordContext, Crypto: SimpleNamespace, title_id: str, destination_directory: str, savePairName: str) -> None:
    embedTimeout = discord.Embed(
        title="Timeout Error:", 
        description="You took too long, sending the file with the format: 'Encrypted'",
        colour=Color.DEFAULT.value)
    embedTimeout.set_footer(text=Embed_t.DEFAULT_FOOTER.value)

    embedFormat = discord.Embed(
        title=f"Format: {savePairName}", 
        description="Choose if you want second layer removed ('Decrypted') or just Sony PFS layer ('Encrypted').", 
        colour=Color.DEFAULT.value)
    embedFormat.set_footer(text="If you want to use the file in a save editor, choose 'Decrypted'!")

    helper = TimeoutHelper(embedTimeout)

    class CryptChoiceButton(discord.ui.View):
        def __init__(self, game: str, start_offset: int, title_id: str) -> None:
            self.game = game
            self.offset = start_offset
            self.title_id = title_id
            super().__init__(timeout=OTHER_TIMEOUT)
                
        async def on_timeout(self) -> None:
            self.disable_all_items()
            await helper.handle_timeout(d_ctx.msg)

        async def on_error(self, error: Exception, _: Item, __: discord.Interaction) -> None:
            self.disable_all_items()
            embedErrb = discord.Embed(title=f"ERROR!", description=f"Could not decrypt: {error}.", colour=Color.DEFAULT.value)
            embedErrb.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            helper.embTimeout = embedErrb
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
            except CryptoError as e:
                raise CryptoError(e)
            except (ValueError, IOError, IndexError):
                raise CryptoError("Invalid save!")
            
            helper.done = True
            
        @discord.ui.button(label="Encrypted", style=discord.ButtonStyle.blurple, custom_id="encrypt")
        async def encryption_callback(self, _: discord.Button, interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(view=None)
            helper.done = True

    if title_id in GTAV_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("GTAV", start_offset=Crypto.Rstar.GTAV_PS_HEADER_OFFSET, title_id=None))
        await helper.await_done()
        
    elif title_id in RDR2_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("RDR2", start_offset=Crypto.Rstar.RDR2_PS_HEADER_OFFSET, title_id=None))
        await helper.await_done()

    elif title_id in XENO2_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("XENO2", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in BL3_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("BL3", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in WONDERLANDS_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("TTWL", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in NDOG_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET, title_id=None))
        await helper.await_done()

    elif title_id in NDOG_COL_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET_COL, title_id=None))
        await helper.await_done()

    elif title_id in NDOG_TLOU2_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("NDOG", start_offset=Crypto.Ndog.START_OFFSET_TLOU2, title_id=None))
        await helper.await_done()

    elif title_id in MGSV_TPP_TITLEID or title_id in MGSV_GZ_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("MGSV", start_offset=None, title_id=title_id))
        await helper.await_done()

    elif title_id in REV2_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("REV2", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in DL1_TITLEID or title_id in DL2_TITLEID or title_id in DL1_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("DL2", start_offset=None, title_id=None))
        await helper.await_done()
    
    elif title_id in RGG_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("RGG", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in DI2_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("DI2", start_offset=None, title_id=None))
        await helper.await_done()

    elif title_id in NMS_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("NMS", start_offset=None, title_id=None))
        await helper.await_done()
    
    elif title_id in TERRARIA_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("TERRARIA", start_offset=None, title_id=None))
        await helper.await_done()
    
    elif title_id in SMT5_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("SMT5", start_offset=None, title_id=None))
        await helper.await_done()
    
    elif title_id in RCUBE_TITLEID:
        await d_ctx.msg.edit(embed=embedFormat, view=CryptChoiceButton("RCUBE", start_offset=None, title_id=None))
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

    except CryptoError as e:
        raise CryptoError(e)
    except (ValueError, IOError, IndexError):
        raise CryptoError("Invalid save!")