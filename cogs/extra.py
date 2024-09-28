import discord
from discord import Option
from discord.ext import commands
from utils.orbis import checkid
from utils.workspace import write_accountid_db, makeWorkspace, WorkspaceError

class Extra(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @discord.slash_command(description="Store your account ID in hexadecimal format.")
    async def store_accountid(
              self, 
              ctx: discord.ApplicationContext,
              account_id: Option(str, description="In hexadecimal format, '0x' prefix is fine and optional.", max_length=18) # type: ignore
            ) -> None:
        workspaceFolders = []
        try: await makeWorkspace(ctx, workspaceFolders, ctx.channel_id)
        except WorkspaceError: return
    
        if len(account_id) == 18:
            if account_id[:2].lower() == "0x":
                account_id = account_id[2:]
            else:
                await ctx.respond("Invalid format!", ephemeral=True)
                return
        
        if not checkid(account_id):
            await ctx.respond("Invalid format!", ephemeral=True)
            return
        
        await write_accountid_db(ctx.author.id, account_id.lower())
        await ctx.respond("Stored!", ephemeral=True)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Extra(bot))