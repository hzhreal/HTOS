import discord
from discord.ext import commands
from network import FTPps, C1socket, SocketError
from utils.constants import (
    IP, PORT_FTP, CON_FAIL, CON_FAIL_MSG, COMMAND_COOLDOWN,
    logger, Color, Embed_t, bot,
    embinit, loadkeyset_emb,
    BASE_ERROR_MSG
)
from utils.helpers import threadButton, errorHandling
from utils.workspace import fetchall_threadid_db, delall_threadid_db, makeWorkspace
from utils.orbis import keyset_to_fw
from utils.instance_lock import INSTANCE_LOCK_global
from utils.exceptions import WorkspaceError

class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    info_group = discord.SlashCommandGroup("info")

    @info_group.command(description="Display the maximum firmware/keyset the hoster's console can mount/unmount a save from.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def keyset(self, ctx: discord.ApplicationContext) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id, skip_gd_check=True)
        except (WorkspaceError, discord.HTTPException): return

        try:
            await ctx.respond(embed=loadkeyset_emb)
        except discord.HTTPException as e:
            logger.exception(f"Error while responding to msg: {e}")
            await INSTANCE_LOCK_global.release(ctx.author.id)
            return

        try:
            keyset = await C1socket.socket_keyset()
            fw = keyset_to_fw(keyset)

            keyset_emb = discord.Embed(
                title="Success",
                description=f"Keyset: {keyset}\nFW: {fw}",
                color=Color.DEFAULT.value
            )
            keyset_emb.set_footer(text=Embed_t.DEFAULT_FOOTER.value)   
            await ctx.edit(embed=keyset_emb)

        except (SocketError, OSError) as e:
            status = "expected"
            if isinstance(e, OSError) and e.errno in CON_FAIL:
                e = CON_FAIL_MSG
            elif isinstance(e, OSError):
                e = BASE_ERROR_MSG
                status = "unexpected"
            await errorHandling(ctx, e, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - ({status})")
        except Exception as e:
            await errorHandling(ctx, BASE_ERROR_MSG, workspaceFolders, None, None, None)
            logger.exception(f"{e} - {ctx.user.name} - (unexpected)")
        finally:
            await INSTANCE_LOCK_global.release(ctx.author.id)

    @discord.slash_command(description="Checks if the bot is functional.")
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def ping(self, ctx: discord.ApplicationContext) -> None:
        try:
            await ctx.defer()
        except discord.HTTPException as e:
            logger.exception(f"Error while deferring: {e}")
            return

        latency = self.bot.latency * 1000
        result = 0

        C1ftp = FTPps(IP, PORT_FTP, "", "", "", "", "", "", "", "")

        ftp_result = socket_result = "Unavailable"

        try:
            await C1ftp.testConnection()
            result += 1
            ftp_result = "Available"
        except OSError as e:
            logger.exception(f"PING: FTP could not connect: {e}")

        try:
            await C1socket.testConnection()
            result += 1
            socket_result = "Available"
        except OSError as e:
            logger.exception(f"PING: SOCKET (Cecie) could not connect: {e}")

        if result == 2:
            color = Color.GREEN.value
        else:
            color = Color.RED.value
        
        desc = (
            f"FTP: **{ftp_result}**\n"
            f"CECIE: **{socket_result}**\n"
            f"Active instances: **{INSTANCE_LOCK_global.instances_len}**/**{INSTANCE_LOCK_global.maximum_instances}**\n"
            f"Latency: **{latency: .2f}** ms"
        )

        embResult = discord.Embed(title=desc, colour=color)
        embResult.set_footer(text=Embed_t.DEFAULT_FOOTER.value)
        try:
            await ctx.respond(embed=embResult)
        except discord.HTTPException as e:
            logger.exception(f"Error while responding to msg: {e}")
            return
    
    @discord.slash_command(description="Send the panel to create threads.")
    @commands.is_owner()
    async def init(self, ctx: discord.ApplicationContext) -> None:
        await ctx.respond("Sending panel...", ephemeral=True)
        await ctx.send(embed=embinit, view=threadButton())
       
    @discord.slash_command(description="Remove all threads created by the bot.")
    @commands.is_owner()
    async def clear_threads(self, ctx: discord.ApplicationContext) -> None:
        await ctx.respond("Clearing threads...", ephemeral=True)
        try:
            db_dict = await fetchall_threadid_db()
            await delall_threadid_db(db_dict)
            
            for _, thread_id in db_dict.items():
                thread = bot.get_channel(thread_id)
                if thread is not None:
                    await thread.delete()
        
        except (discord.Forbidden, WorkspaceError) as e:
            logger.error(f"Error clearing all threads: {e}")
        
        await ctx.respond(f"Cleared {len(db_dict)} thread(s)!", ephemeral=True)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Misc(bot))