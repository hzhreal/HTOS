import discord
from discord.ext import commands
from io import BytesIO
from network.socket_functions import SDKeyUnsealer, SocketError
from utils.workspace import makeWorkspace, WorkspaceError
from utils.helpers import errorHandling
from utils.constants import logger, Color, BASE_ERROR_MSG, IP, PORTSOCKET_SEALEDKEY

class Sealed_Key(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    sealed_key_group = discord.SlashCommandGroup("sealed_key")

    @sealed_key_group.command(description="Decrypt a sealed key (.bin file).")
    async def decrypt(self, ctx: discord.ApplicationContext, sealed_key: discord.Attachment) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        embLoad = discord.Embed(title="Loading",
                          description=f"Loading {sealed_key.filename}...",
                          colour=Color.DEFAULT.value)
        embLoad.set_footer(text="Made by hzh.")

        await ctx.respond(embed=embLoad)

        if sealed_key.size != 96:
            e = "Invalid size: must be 96 bytes!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return
        
        elif PORTSOCKET_SEALEDKEY is None:
            e = "Unavailable."
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        enc_key = bytearray(await sealed_key.read())

        try:
            unsealer = SDKeyUnsealer(IP, PORTSOCKET_SEALEDKEY)
            dec_key = await unsealer.upload_key(enc_key)

            if isinstance(dec_key, str):
                # this means error message, so raise expected error
                raise SocketError(dec_key)

            embdec= discord.Embed(title="Finished",
                          description=f"Successfully decrypted {sealed_key.filename}.",
                          colour=Color.DEFAULT.value)
            embdec.set_footer(text="Made by hzh.")

            await ctx.edit(embed=embdec)
            await ctx.respond(file=discord.File(BytesIO(dec_key), filename=sealed_key.filename))
        except SocketError as e:
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            return

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sealed_Key(bot))