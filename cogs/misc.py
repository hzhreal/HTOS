import discord
from discord.ext import commands
from network import FTPps, SocketPS
from utils.constants import (
    IP, PORT, PORTSOCKET,
    logger, Color, bot,
    embinit
)
from utils.helpers import threadButton
from utils.workspace import fetchall_threadid_db, delall_threadid_db, WorkspaceError

class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Checks if the bot is functional.")
    async def ping(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer()
        result = 0
        latency = self.bot.latency * 1000
        C1ftp = FTPps(IP, PORT, None, None, None, None, None, None, None, None)
        C1socket = SocketPS(IP, PORTSOCKET)

        try:
            await C1ftp.testConnection()
            result += 1
        except OSError as e:
            logger.exception(f"PING: FTP could not connect: {e}")

        try:
            await C1socket.testConnection()
            result += 1
        except OSError as e:
            logger.exception(f"PING: SOCKET could not connect: {e}")

        if result == 2:
            color = Color.GREEN.value
        else:
            color = Color.RED.value
        
        embResult = discord.Embed(title=f"Connections: {result}/2\nLatency: {latency: .2f}ms", colour=color)
        embResult.set_footer(text="Made by hzh.")
        await ctx.respond(embed=embResult)
    
    @discord.slash_command(description="Send the panel to create threads.")
    @commands.is_owner()
    async def init(self, ctx: discord.ApplicationContext) -> None:
        await ctx.respond("Sending panel...", ephemeral=True)
        await ctx.send(embed=embinit, view=threadButton())

    @init.error
    async def on_init_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)
       
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
        
        await ctx.respond(f"Cleared {len(db_dict)} threads!", ephemeral=True)
    
    @clear_threads.error
    async def on_clear_threads_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)
       

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Misc(bot))