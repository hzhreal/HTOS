import discord
from discord.ext import commands
from io import BytesIO
from network.socket_functions import SocketPS, SocketError
from utils.workspace import makeWorkspace
from utils.helpers import errorHandling
from utils.constants import logger, Color, Embed_t, BASE_ERROR_MSG, IP, PORT_CECIE, SEALED_KEY_ENC_SIZE, COMMAND_COOLDOWN
from utils.orbis import PfsSKKey
from utils.instance_lock import INSTANCE_LOCK_global
from utils.exceptions import WorkspaceError

class Sealed_Key(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    sealed_key_group = discord.SlashCommandGroup("sealed_key")

    @sealed_key_group.command(description="Decrypt a sealed key (.bin file).")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
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
        try:
            await ctx.respond(embed=embLoad)
        except discord.HTTPException as e:
            logger.exception(f"Error while responding to interaction: {e}")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        if sealed_key.size != SEALED_KEY_ENC_SIZE:
            e = f"Invalid size: must be {SEALED_KEY_ENC_SIZE} bytes!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        enc_key = bytearray(await sealed_key.read())
        sealedkey_t = PfsSKKey(enc_key)
    
        if not sealedkey_t.validate():
            e = "Invalid sealed key!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
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
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sealed_Key(bot))