import discord
from utils.constants import bot, TOKEN
from utils.workspace import startup
from utils.helpers import threadButton

@bot.event
async def on_ready() -> None:
    startup()
    bot.add_view(threadButton()) # make view persistent
    print(
        f"Bot is ready, invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot"
    )

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
    "decrypt",
    "encrypt",
    "misc",
    "quick",
    "reregion",
    "resign",
    "sfo"
]

if __name__ == "__main__":
    for cog in cogs_list:
        print(f"Loading cog: {cog}...")
        bot.load_extension(f"cogs.{cog}")
        print(f"Loaded cog: {cog}.")
    
    print("Starting bot...")
    bot.run(TOKEN)