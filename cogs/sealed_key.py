import discord
from discord.ext import commands
from io import BytesIO
from network.socket_functions import SocketPS, SocketError
from utils.workspace import makeWorkspace, WorkspaceError
from utils.helpers import errorHandling
from utils.constants import logger, Color, Embed_t, BASE_ERROR_MSG, IP, PORT_CECIE, SEALED_KEY_ENC_SIZE
from utils.orbis import PfsSKKey

class Sealed_Key(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    sealed_key_group = discord.SlashCommandGroup("sealed_key")

    @sealed_key_group.command(description="Decrypt a sealed key (.bin file).")
    async def decrypt(self, ctx: discord.ApplicationContext, sealed_key: discord.Attachment) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        embLoad = discord.Embed(
            title="Loading",
            description=f"Loading {sealed_key.filename}...",
            colour=Color.DEFAULT.value
        )
        embLoad.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        await ctx.respond(embed=embLoad)

        if sealed_key.size != SEALED_KEY_ENC_SIZE:
            e = f"Invalid size: must be {SEALED_KEY_ENC_SIZE} bytes!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        enc_key = bytearray(await sealed_key.read())
        sealedkey_t = PfsSKKey(enc_key)
    
        if not sealedkey_t.validate():
            e = "Invalid sealed key!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        try:
            C1socket = SocketPS(IP, PORT_CECIE)
            await C1socket.socket_decryptsdkey(sealedkey_t)

            embdec = discord.Embed(
                title="Finished",
                description=f"Successfully decrypted {sealed_key.filename}.",
                colour=Color.DEFAULT.value
            )
            embdec.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
            await ctx.edit(embed=embdec)

            await ctx.respond(file=discord.File(BytesIO(sealedkey_t.dec_key), filename=sealed_key.filename))
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