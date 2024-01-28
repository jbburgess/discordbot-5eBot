'''
A Discord bot for looking up information related to D&D 5th Edition.

Currently only supports rolling dice in NdN format (e.g., 1d20, 2d4...).

Functions:
    roll(dice: str) -> str
'''

# Importing required modules
import argparse
import asyncio
import json
import logging
from pathlib import Path
import random
import re
import typing
import discord
from discord import app_commands
import modules.spells as spells
import modules.discord_views as discord_views

# Parse command line arguments
parser = argparse.ArgumentParser(description='A Discord bot for looking up information related to D&D 5th Edition.')
parser.add_argument('--test', action='store_true', help='Enable test and debug mode. Only "test" guild(s) will be updated.')
args = parser.parse_args()

# Initialize logging
logger = logging.getLogger(__name__)

stderr_log_handler = logging.StreamHandler()
file_log_handler = logging.FileHandler('logfile.log')

if args.test:
    stderr_log_handler.setLevel(logging.DEBUG)
    file_log_handler.setLevel(logging.DEBUG)
else:
    stderr_log_handler.setLevel(logging.INFO)
    file_log_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_log_handler.setFormatter(formatter)
file_log_handler.setFormatter(formatter)

logger.addHandler(stderr_log_handler)
logger.addHandler(file_log_handler)

# Retrieve JSON config file.
root_dir = Path(Path(__file__).parent)
with open("config.json", encoding = "utf8") as json_data_file:
    config = json.load(json_data_file)

# Parse config and initialize global variables.
TOKEN = config['discord']['token']
CHARLIMIT = config['discord']['charlimit']
TEMPLATESDIR  = config['environment']['directory']['templates']

# Set up test/prod mode
if args.test:
    logger.info('Test mode enabled.')
    logger.info('Only "test" guild(s) will be updated.')
    guild_ids = config['discord']['guildids']['test']
    logging.basicConfig(level=logging.DEBUG)
else:
    logger.info('Test mode not enabled.')
    logger.info('The "prod" guild(s) will be updated.')
    guild_ids = config['discord']['guildids']['prod']
    logging.basicConfig(level=logging.INFO)
guild_objs = [discord.Object(id = guild_id) for guild_id in guild_ids]

# Define intents for bot.
intents = discord.Intents().all()
intents.members = True
intents.message_content = True

# Initialize bot.
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Bot command to roll dice
@tree.command(
    name = "roll",
    description = "Roll dice in NdN format. Add an optional modifier in +/-N format.",
    guilds = guild_objs
)
@app_commands.describe(dice="The dice to roll, in NdN format (e.g., 1d20, 2d4...).")
async def roll(interaction: discord.Interaction, dice: str, modifier: typing.Optional[str] = None):
    '''
    Input dice in NdN format, returns the roll. Supports adding a modifier in +/-N format.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    dice : str
        The dice to roll.
    modifier : str, optional
        The modifier to add to the roll
    '''
    # Define the regex pattern for a dice roll (e.g., 1d6, 2d4, etc.)
    dice_pattern = r'^\d+d\d+$'
    modifier_pattern = r'^[+-]\d+$'

    # Check if the dice parameter matches the pattern
    if not re.match(dice_pattern, dice):
        message = 'Invalid `dice` format! Format has to be in NdN!'
        combined_pattern = r'^\d+d\d+[+-]\d+$'
        if re.match(combined_pattern, dice):
            message += '\nOops, you put a modifier in the `dice` parameter. Please specify the modifier separately in the `modifier` parameter!'
        await interaction.response.send_message(message, ephemeral = True)
        return

    # Check if the modifier parameter matches the pattern
    if modifier and not re.match(modifier_pattern, modifier):
        await interaction.response.send_message('Invalid `modifier` format! Format has to be in +/-N!', ephemeral = True)
        return

    # Roll the dice
    rolls, limit = map(int, dice.split('d'))
    diceroll = [random.randint(1, limit) for r in range(rolls)]

    # Format the result
    if modifier:
        result = f'Rolling {dice}{modifier}...\n{interaction.user} rolled {", ".join(map(str,diceroll))}.'
    else:
        result = f'Rolling {dice}...\n{interaction.user} rolled {", ".join(map(str,diceroll))}.'

    # Specify the total if rolling multiple dice.
    if modifier:
        result += f"\n{interaction.user}'s total (with modifier) is {sum(diceroll) + int(modifier)}."
    elif rolls > 1:
        result += f"\n{interaction.user}'s total is {sum(diceroll)}."

    await interaction.response.send_message(result)

# Bot command to lookup spells
@tree.command(
    name = "spell",
    description = "Look up a spell by name (source optional). Only exact matches work currently.",
    guilds = guild_objs
)
@app_commands.describe(
    name="The name of the spell to look up. Exact matches only.",
    source="The source of the spell to look up."
)
async def spell(interaction: discord.Interaction, name: str, source: typing.Optional[str] = None):
    '''
    Look up a spell by name. You can also specify a source to narrow down the search. Only exact matches work currently.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    name : str
        The name of the spell to look up.
    source : str, optional
        The source of the spell to look up.
    '''
    # Initialize the spell object
    if source:
        spell_instance = spells.Spell(name, source)
    else:
        spell_instance = spells.Spell(name)

    # If provided, check if the source exists
    if source and not spell_instance.source_exists():
        await interaction.response.send_message(f'Source `{source}` not found! Format should be in the form of "PHB", "XGtE", etc. Only exact matches work currently, sorry.', ephemeral = True)
        return

    # Check if the spell exists
    if not spell_instance.spell_exists():
        await interaction.response.send_message(f'Spell `{name}` not found! Format should be in the form of "Fireball", "Cure Wounds", etc. Only exact matches work currently, sorry.', ephemeral = True)
        return

    # Send the formatted spell information
    if spell_instance.spell_markdown is not None:
        # If the spell is too long, split it into multiple messages
        if len(spell_instance.spell_markdown) > CHARLIMIT:
            # If the description body alone is too long, split into multiple messages based on newlines
            # Otherwise, split into two messages at the "---" separator
            if len(spell_instance.spell_description) > CHARLIMIT:
                parts = []
                content = spell_instance.spell_markdown
                while len(content) > CHARLIMIT:
                    split_index = content[:CHARLIMIT].rfind("\n")
                    if split_index == -1:  # No newline found, split at the limit
                        split_index = CHARLIMIT
                    parts.append(content[:split_index])
                    content = content[split_index:]
                parts.append(content)  # Add the remaining content
            else:
                parts = spell_instance.spell_markdown = spell_instance.spell_markdown.split('---')

            for part in parts:
                if part == parts[0]:
                    await interaction.response.send_message(part)
                else:
                    await interaction.followup.send(part)
        else:
            await interaction.response.send_message(spell_instance.spell_markdown)
    else:
        await interaction.response.send_message(f'Sorry, spell information did not format properly! Here is the raw data:\n{spell_instance.spell_dict}')

def get_weather(weather: int):
    '''
    Convert the roll integer to a friendly weather description.

    Parameters
    ----------
    day : int
        The day to get the weather for.
    '''
    # Generate the weather description
    if weather == 1:
        weather = "Deluge"
    elif weather == 2:
        weather = "Sweltering"
    elif int(weather) in range(3, 8):
        weather = "Normal"
    else:
        raise ValueError("Weather value out of range!")

    return weather

# Bot command to start a new Chultan day.
@tree.command(
    name = "newday",
    description = "Start a new day in Chult.",
    guilds = guild_objs
)
@app_commands.describe(
    day = "Which day are we on?",
    location = "Where are we?",
    weather = "What is the weather like?",
    forecast = "What is the weather forecast for later today?",
    status = "What is the party's status?"
)
#async def roll(interaction: discord.Interaction, day: int):
async def newday(interaction: discord.Interaction, day: int, location: str, weather: int, forecast: int, status: str):
    """
    Start a new day in Chult.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    day : int
        Which day are we on?
    location : str
        Where are we?
    weather : int
        What is the weather like?
    forecast : int
        What is the weather forecast for later today?
    status : str
        What is the party's status?
    """
    
    #Load templates
    templates_dir = Path(root_dir, TEMPLATESDIR)
    with open(templates_dir.joinpath('newday.md'), encoding='utf8') as template_file:
                newday_template = template_file.read()

    # Generate the starting log Markdown
    newday_log = newday_template.format(
        day = day,
        location = location,
        weather = get_weather(weather),
        status = status
    )

    await interaction.response.send_message(newday_log)
    await interaction.followup.send(f'Forecast: {get_weather(forecast)}', ephemeral = True)

# Login and sync command tree
@bot.event
async def on_ready():
    '''Login and sync command tree'''
    for obj in guild_objs:
        await tree.sync(guild = obj)
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
