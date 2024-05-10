import discord
from discord.ext import commands
from io import BytesIO
from network.socket_functions import SDKeyUnsealer, SocketError
from utils.workspace import makeWorkspace, WorkspaceError
from utils.helpers import errorHandling
from utils.constants import logger, Color, BASE_ERROR_MSG, IP, PORT_SDKEYUNSEALER, SEALED_KEY_ENC_SIZE

class PfsSKKey:
    def __init__(self, data: bytearray) -> None:
        assert len(data) == self.SIZE

        self.MAGIC   = data[:0x08]
        self.VERSION = data[0x08:0x10]
        self.IV      = data[0x10:0x20]
        self.KEY     = data[0x20:0x40]
        self.SHA256  = data[0x40:0x60]

        self.data    = data

    SIZE = 0x60
    MAGIC_VALUE = b"pfsSKKey"

    def validate(self) -> bool:
        if self.MAGIC != self.MAGIC_VALUE:
            return False
        return True
    
    def as_bytearray(self) -> bytearray:
        return self.data       

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

        if sealed_key.size != SEALED_KEY_ENC_SIZE:
            e = f"Invalid size: must be {SEALED_KEY_ENC_SIZE} bytes!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return
        
        elif PORT_SDKEYUNSEALER is None:
            e = "Unavailable."
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        enc_key = bytearray(await sealed_key.read())
        enc_key = PfsSKKey(enc_key)
    
        if not enc_key.validate():
            e = "Invalid sealed key!"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            return

        try:
            unsealer = SDKeyUnsealer(IP, PORT_SDKEYUNSEALER)
            dec_key = await unsealer.upload_key(enc_key.as_bytearray())

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