import discord
from discord.ext import commands
from io import BytesIO
from network.socket_functions import C1socket, SocketError
from utils.workspace import make_workspace
from utils.helpers import error_handling
from utils.constants import logger, BASE_ERROR_MSG, SEALED_KEY_ENC_SIZE, COMMAND_COOLDOWN
from utils.embeds import embLoad, embdec
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
        workspace_folders = []
        try: await make_workspace(ctx, workspace_folders, ctx.channel_id, skip_gd_check=True)
        except (WorkspaceError, discord.HTTPException): return

        emb = embLoad.copy()
        emb.description = emb.description.format(filename=sealed_key.filename)
        try:
            await ctx.respond(embed=emb)
        except discord.HTTPException as e:
            logger.exception(f"Error while responding to interaction: {e}")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        if sealed_key.size != SEALED_KEY_ENC_SIZE:
            e = f"Invalid size: must be {SEALED_KEY_ENC_SIZE} bytes!"
            await error_handling(ctx, e, workspace_folders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        enc_key = bytearray(await sealed_key.read())
        sealedkey_t = PfsSKKey(enc_key)
    
        if not sealedkey_t.validate():
            e = "Invalid sealed key!"
            await error_handling(ctx, e, workspace_folders, None, None, None)
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        try:
            await C1socket.socket_decryptsdkey(sealedkey_t)

            emb = embdec.copy()
            emb.description = emb.description.format(filename=sealed_key.filename)
            await ctx.edit(embed=emb)

            await ctx.respond(file=discord.File(BytesIO(sealedkey_t.dec_key), filename=sealed_key.filename))
        except SocketError as e:
            await error_handling(ctx, e, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (expected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        except Exception as e:
            await error_handling(ctx, BASE_ERROR_MSG, workspace_folders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return
        await INSTANCE_LOCK_global.release(ctx.author.id)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Sealed_Key(bot))
