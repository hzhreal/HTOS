from dotenv import load_dotenv
load_dotenv()

import discord
import argparse
from discord.ext import commands
from utils.constants import bot, TOKEN
from utils.workspace import WorkspaceOpt, startup, check_version
from utils.helpers import threadButton
from utils.conversions import round_half_up

workspace_opt = WorkspaceOpt()

@bot.event
async def on_ready() -> None:
    from google_drive import check_GDrive
    startup(workspace_opt)
    await check_version()
    bot.add_view(threadButton()) # make view persistent
    check_GDrive.start() # start gd daemon
    print(
        f"Bot is ready, invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot"
    )

@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException) -> None:
    match error:
        case commands.CommandOnCooldown():
            await ctx.respond(f"You are on cooldown. Try again in {round_half_up(error.retry_after)} seconds.", ephemeral=True)
        case commands.NotOwner():
            await ctx.respond("You are unauthorized to use this command.", ephemeral=True)

@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if message.content == "hello":
        await message.channel.send("hi")

    await bot.process_commands(message)

cogs_list = [
    "change",
    "convert",
    "createsave",
    "decrypt",
    "encrypt",
    "extra",
    "misc",
    "quick",
    "reregion",
    "resign",
    "sealed_key",
    "sfo",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore-startup", action="store_true")
    args = parser.parse_args()
    if args.ignore_startup:
        workspace_opt.ignore_startup = True

    for cog in cogs_list:
        print(f"Loading cog: {cog}...")
        bot.load_extension(f"cogs.{cog}")
        print(f"Loaded cog: {cog}.")

    print("Starting bot...\n\n")
    bot.run(TOKEN)
