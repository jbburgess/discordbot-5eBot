'''
A Discord bot for looking up information related to D&D 5th Edition.

Currently only supports rolling dice in NdN format (e.g., 1d20, 2d4...).

Functions:
    roll(dice: str) -> str
'''

# Importing required modules
import json
import random
import discord
from discord import app_commands

# Retrieve JSON config file.
with open("config.json",encoding="utf8") as json_data_file:
    config = json.load(json_data_file)

# Parse config and initialize global variables.
TOKEN = config['discord']['token']

# Define intents for bot.
intents = discord.Intents().all()
intents.members = True
intents.message_content = True

# Initialize bot.
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Bot command to roll dice
@tree.command(
    name="roll",
    description="Roll dice in NdN format (e.g., 1d20, 2d4...). Modifiers not supported.",
    guilds=(discord.Object(id=844428356765745223), discord.Object(id=761264439131242536))
)
async def roll(interaction, dice: str):
    '''Input dice in NdN format, returns the roll.'''
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await interaction.response.send_message('Format has to be in NdN!')
        return

    diceroll = [random.randint(1, limit) for r in range(rolls)]
    result = f'Rolling {dice}...\nYou rolled {", ".join(map(str,diceroll))}.'

    if rolls > 1:
        result += f'\nYour total is {sum(diceroll)}.'

    await interaction.response.send_message(result)

# Login and sync command tree
@bot.event
async def on_ready():
    '''Login and sync command tree'''
    await tree.sync(guild=discord.Object(id=844428356765745223))
    await tree.sync(guild=discord.Object(id=761264439131242536))
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

# Say hello!
@bot.event
async def on_message(message):
    '''Say hello!'''
    # Check who sent the message
    if message.author == bot.user:
        return

    msg = message.content
    if msg.startswith('Hello'):
        await message.channel.send("Hello!")

# Running bot with token
bot.run(TOKEN)
