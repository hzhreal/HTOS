import discord
import json
from discord import Option
from discord.ext import commands
from io import BytesIO
from utils.constants import logger
from utils.orbis import checkid
from utils.workspace import write_accountid_db, blacklist_write_db, blacklist_del_db, blacklist_delall_db, blacklist_fetchall_db, makeWorkspace
from utils.instance_lock import INSTANCE_LOCK_global
from utils.exceptions import WorkspaceError

class Extra(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    blacklist_group = discord.SlashCommandGroup("blacklist")

    @blacklist_group.command(description="Add entry to blacklist.")
    @commands.is_owner()
    async def add(
              self,
              ctx: discord.ApplicationContext,
              ps_accountid: Option(str, description="In hexadecimal format, '0x prefix is fine and optional.", max_length=18, default=""), # type: ignore
              user: Option(discord.User, default="") # type: ignore
            ) -> None:

            await ctx.defer(ephemeral=True)
            if ps_accountid == "" and user == "":
                await ctx.respond("No values inputted!")
                return
            
            if ps_accountid != "":
                if len(ps_accountid) == 18:
                    if ps_accountid[:2].lower() == "0x":
                        ps_accountid = ps_accountid[2:]
                    else:
                        await ctx.respond("PS account ID in invalid format!")
                        return

                if not checkid(ps_accountid):
                    await ctx.respond("PS account ID in invalid format!")
                    return

            try:
                await blacklist_write_db(user if user != "" else None, ps_accountid if ps_accountid != "" else None)
                await ctx.respond("Added!")
            except WorkspaceError as e:
                await ctx.respond(e)
    
    @blacklist_group.command(description="Remove entry from blacklist.")
    @commands.is_owner()
    async def remove(
              self,
              ctx: discord.ApplicationContext,
              ps_accountid: Option(str, description="In hexadecimal format, '0x prefix is fine and optional.", max_length=18, default=""), # type: ignore
              user: Option(discord.User, default="") # type: ignore
            ) -> None:

        await ctx.defer(ephemeral=True)
        if ps_accountid == "" and user == "":
            await ctx.respond("No values inputted!")
            return
        
        if ps_accountid != "":
            if len(ps_accountid) == 18:
                if ps_accountid[:2].lower() == "0x":
                    ps_accountid = ps_accountid[2:]
                else:
                    await ctx.respond("PS account ID in invalid format!")
                    return

            if not checkid(ps_accountid):
                await ctx.respond("PS account ID in invalid format!")
                return
        
        try:
            await blacklist_del_db(user.id if user != "" else None, ps_accountid if ps_accountid != "" else None)
            await ctx.respond("Removed!")
        except WorkspaceError as e:
            await ctx.respond(e)

    @blacklist_group.command(description="Remove all entries from blacklist.")
    @commands.is_owner()
    async def remove_all(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await blacklist_delall_db()
            await ctx.respond("Removed all entries!")
        except WorkspaceError as e:
            await ctx.respond(e)

    @blacklist_group.command(description="List all entries in blacklist.")
    @commands.is_owner()
    async def show(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)
        try:
            entries = await blacklist_fetchall_db()
            data = json.dumps(entries, indent=4).encode("utf-8")
            await ctx.respond(file=discord.File(BytesIO(data), filename="blacklist.json"))
        except WorkspaceError as e:
            await ctx.respond(e)

    @discord.slash_command(description="Store your account ID in hexadecimal format.")
    async def store_accountid(
              self, 
              ctx: discord.ApplicationContext,
              account_id: Option(str, description="In hexadecimal format, '0x' prefix is fine and optional.", max_length=18) # type: ignore
            ) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return

        msg = ctx
        
        try:
            msg = await ctx.edit(content="Adding...")
            msg = await ctx.fetch_message(msg.id)
            
            if len(account_id) == 18:
                if account_id[:2].lower() != "0x":
                    raise ValueError()
                account_id = account_id[2:]
            
            if not checkid(account_id):
                raise ValueError()
            
            await write_accountid_db(ctx.author.id, account_id.lower())
            await msg.edit(content="Stored!")
        except ValueError:
            try:
                await msg.edit(content="Invalid format!")
            except discord.HTTPException as e:
                logger.exception(f"Error responding to msg: {e}")
        except WorkspaceError as e:
            try:
                await msg.edit(content=e)
            except discord.HTTPException as e:
                logger.exception(f"Error responding to msg: {e}")
        except discord.HTTPException as e:
            logger.exception(e)
        finally:
            await INSTANCE_LOCK_global.release()
    
    @add.error
    async def on_add_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)
    
    @remove.error
    async def on_remove_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)
    
    @remove_all.error
    async def on_remove_all_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)

    @show.error
    async def on_show_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
        if isinstance(error, commands.NotOwner):
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Extra(bot))