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
        await interaction.response.send_message('Invalid `dice` format! Format has to be in NdN!')
        return

    # Check if the modifier parameter matches the pattern
    if modifier and not re.match(modifier_pattern, modifier):
        await interaction.response.send_message('Invalid `modifier` format! Format has to be in +/-N!')
        return

    # Roll the dice
    rolls, limit = map(int, dice.split('d'))
    diceroll = [random.randint(1, limit) for r in range(rolls)]

    # Format the result
    if modifier:
        result = f'Rolling {dice}{modifier}...\nYou rolled {", ".join(map(str,diceroll))}.'
    else:
        result = f'Rolling {dice}...\nYou rolled {", ".join(map(str,diceroll))}.'

    # Specify the total if rolling multiple dice.
    if modifier:
        result += f'\nYour total (with modifier) is {sum(diceroll) + int(modifier)}.'
    elif rolls > 1:
        result += f'\nYour total is {sum(diceroll)}.'

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
        await interaction.response.send_message(f'Source `{source}` not found! Format should be in the form of "PHB", "XGtE", etc. Only exact matches work currently, sorry.')
        return

    # Check if the spell exists
    if not spell_instance.spell_exists():
        await interaction.response.send_message(f'Spell `{name}` not found! Format should be in the form of "Fireball", "Cure Wounds", etc. Only exact matches work currently, sorry.')
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
        await interaction.response.send_message(f'Sorry, spell information not formatted properly! Here is the raw data:\n{spell_instance.spell_dict}')

# Bot command to start a new Chultan day.
@tree.command(
    name = "newday",
    description = "Generate and start a new day in Chult, maybe continue an expedition, log it all at the end.",
    guilds = guild_objs
)
@app_commands.describe(day = "Which day are we on?")
#async def roll(interaction: discord.Interaction, day: int):
async def select_menu(interaction: discord.Interaction, day: int):
    """A command to test our view"""
    
    #Load templates
    templates_dir = Path(root_dir, 'templates')
    with open(templates_dir.joinpath('startday-base.md'), encoding='utf8') as template_file:
                startday_base = template_file.read()
    with open(templates_dir.joinpath('startday-travel.md'), encoding='utf8') as template_file:
                startday_travel = template_file.read()
    
    options_location = [
            discord.SelectOption(label='Port Nyanzaru', description="We're just chillin'.", emoji=f'{chr(127960)}{chr(65039)}'),
            discord.SelectOption(label='Road/Coast/Lake', description='Normal terrain, no difficulty.', emoji=f'{chr(127958)}{chr(65039)}'),
            discord.SelectOption(label='Jungle/River', description='Terrain is a little difficult.', emoji=f'{chr(127796)}'),
            discord.SelectOption(label='Mountain/Swamp/Wasteland', description='Very diificult terrain!', emoji=f'{chr(127956)}{chr(65039)}'),
        ]
    options_locationnormal = [
        discord.SelectOption(label='Road', emoji=f'{chr(128739)}{chr(65039)}'),
        discord.SelectOption(label='Coast', emoji=f'{chr(127958)}{chr(65039)}'),
        discord.SelectOption(label='Lake', emoji=f'{chr(127754)}'),
    ]
    options_locationmedium = [
        discord.SelectOption(label='Jungle', emoji=f'{chr(127796)}'),
        discord.SelectOption(label='River', emoji=f'{chr(127966)}{chr(65039)}'),
    ]
    options_locationdifficult = [
        discord.SelectOption(label='Mountain', emoji=f'{chr(9968)}{chr(65039)}'),
        discord.SelectOption(label='Swamp', emoji=f'{chr(129439)}'),
        discord.SelectOption(label='Wasteland', emoji=f'{chr(127964)}{chr(65039)}'),
    ]
    
    options_weather = [
            discord.SelectOption(label='Normal', description='Normal weather today (so...hot and rainy).', emoji=f"{chr(9728)}{chr(65039)}"),
            discord.SelectOption(label='Sweltering', description='The heat today is sweltering!', emoji=f"{chr(129397)}"),
            discord.SelectOption(label='Deluge', description='Is there a typhoon coming through?', emoji=f"{chr(127783)}{chr(65039)}")
        ]

    options_bool = [
            discord.SelectOption(label='Yes', emoji=f'{chr(9989)}'),
            discord.SelectOption(label='No', emoji=f'{chr(10060)}')
        ]

    notes_modal = discord_views.BaseModal(title=f"Starting day {day}...")
    text_input = discord.ui.TextInput(label="First, any additional notes for today?", placeholder="Enter additional notes here...", min_length=1, max_length=256)
    notes_modal.add_item(text_input)

    future = asyncio.Future()

    async def callback(interaction: discord.Interaction) -> None:
        inputted_notes = text_input.value
        future.set_result(inputted_notes)
        await interaction.response.defer()

    notes_modal.on_submit = callback
    await interaction.response.send_modal(notes_modal)

    inputted_notes = await future

    if inputted_notes != "":
        inputted_notes = f"Additional Notes: {inputted_notes}"
    
    # Create the location view
    view = discord_views.SelectMenu(interaction.user, options_location, "Select today's location...")
    await interaction.followup.send(view=view, ephemeral=True)
    selected_location = await view.wait_for_selection()

    if selected_location == "Road/Coast/Lake":
        # Create the normal location drill-down view
        view = discord_views.SelectMenu(interaction.user, options_locationnormal, "Select the specific location...")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_locationspecific = await view.wait_for_selection()
    elif selected_location == "Jungle/River":
        # Create the medium location drill-down view
        view = discord_views.SelectMenu(interaction.user, options_locationmedium, "Select the specific location...")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_locationspecific = await view.wait_for_selection()
    elif selected_location == "Mountain/Swamp/Wasteland":
        # Create the difficult location drill-down view
        view = discord_views.SelectMenu(interaction.user, options_locationdifficult, "Select the specific location...")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_locationspecific = await view.wait_for_selection()
    else:
        selected_locationspecific = selected_location
    
    # Create the weather view
    view = discord_views.SelectMenu(interaction.user, options_weather, "Select today's weather...")
    await interaction.followup.send(view=view, ephemeral=True)
    selected_weather = await view.wait_for_selection()

    if selected_location != "Port Nyanzaru":
        # Create the food view
        view = discord_views.SelectMenu(interaction.user, options_bool, "Does the party have enough food?")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_enoughfood = await view.wait_for_selection()

        # Create the water view
        view = discord_views.SelectMenu(interaction.user, options_bool, "Does the party have enough water?")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_enoughwater = await view.wait_for_selection()

        # Create the insect spray view
        view = discord_views.SelectMenu(interaction.user, options_bool, "Does the party have enough insect spray?")
        await interaction.followup.send(view=view, ephemeral=True)
        selected_enoughspray = await view.wait_for_selection()

        # Generate the travel part of the template Markdown
        template_travel = startday_travel.format(
            enoughfood = selected_enoughfood,
            enoughwater = selected_enoughwater,
            enoughspray = selected_enoughspray
        )
    else:
        template_travel = ""
    
    # Generate the starting log Markdown
    starting_log = startday_base.format(
        day = day,
        location = selected_locationspecific,
        weather = selected_weather,
        template_travel = template_travel,
        notes = inputted_notes
    )

    await interaction.followup.send(starting_log)

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
