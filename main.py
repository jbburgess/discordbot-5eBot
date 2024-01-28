'''
A Discord bot for looking up information related to D&D 5th Edition.

Currently only supports rolling dice in NdN format (e.g., 1d20, 2d4...).

Functions:
    roll(dice: str) -> str
'''

# Importing required modules
import argparse
import asyncio
import glob
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
templates_dir = Path(root_dir, TEMPLATESDIR)

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
@app_commands.choices(
    weather = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ],
    forecast = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ]
)
@app_commands.checks.has_role("Dungeon Master")
async def newday(interaction: discord.Interaction, day: int, location: str, weather: str, forecast: str, status: str):
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
    with open(templates_dir.joinpath('newday.md'), encoding='utf8') as template_file:
        newday_template = template_file.read()

    # Generate the starting log Markdown
    newday_log = newday_template.format(
        day = day,
        location = location,
        weather = weather,
        status = status
    )

    await interaction.response.send_message(newday_log)
    await interaction.followup.send(f'Forecast: {forecast}', ephemeral = True)

# Bot command to ask party to react to the checklist.
@tree.command(
    name = "checklist",
    description = "Prompt the party to complete the checklist for the day.",
    guilds = guild_objs
)
@app_commands.checks.has_role("Dungeon Master")
async def checklist(interaction: discord.Interaction):
    '''
    Prompt the party to complete the checklist for the day.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    '''
    #Load templates
    checklist_templates = glob.glob(f'{Path(templates_dir, "checklist_*.md")}')
    for file in checklist_templates:
        with open(file, encoding='utf8') as template_file:
            markdown = template_file.read()

        if file == checklist_templates[0]:
            await interaction.response.send_message(markdown)
        else:
            await interaction.followup.send(markdown)

# Bot command to attempt to travel to a different hex.
@tree.command(
    name = "travel",
    description = "Attempt to travel to a new location hex in Chult.",
    guilds = guild_objs
)
@app_commands.describe(
    weather = "What is the weather like?",
    forecast = "What is the weather forecast for later today?",
    start_hex = "Where is the party?",
    target_hex = "Where is the party trying to go?",
    pace = "What is the traveling pace?",
    nav_check = "What was the result of the navigator's survival check?"
)
@app_commands.choices(
    weather = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ],
    forecast = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ],
    start_hex = [
        app_commands.Choice(name = "Town", value = "town"),
        app_commands.Choice(name = "Fort", value = "fort"),
        app_commands.Choice(name = "Camp", value = "camp"),
        app_commands.Choice(name = "Road", value = "road"),
        app_commands.Choice(name = "Coast", value = "coast"),
        app_commands.Choice(name = "Lake", value = "lake"),
        app_commands.Choice(name = "Jungle", value = "jungle"),
        app_commands.Choice(name = "River", value = "river"),
        app_commands.Choice(name = "Mountains", value = "mountains"),
        app_commands.Choice(name = "Swamp", value = "swamp"),
        app_commands.Choice(name = "Wasteland", value = "wasteland")
    ],
    target_hex = [
        app_commands.Choice(name = "Town", value = "town"),
        app_commands.Choice(name = "Fort", value = "fort"),
        app_commands.Choice(name = "Camp", value = "camp"),
        app_commands.Choice(name = "Road", value = "road"),
        app_commands.Choice(name = "Coast", value = "coast"),
        app_commands.Choice(name = "Lake", value = "lake"),
        app_commands.Choice(name = "Jungle", value = "jungle"),
        app_commands.Choice(name = "River", value = "river"),
        app_commands.Choice(name = "Mountains", value = "mountains"),
        app_commands.Choice(name = "Swamp", value = "swamp"),
        app_commands.Choice(name = "Wasteland", value = "wasteland"),
        app_commands.Choice(name = "N/A", value = "na")
    ],
    pace = [
        app_commands.Choice(name = "Normal", value = "normal"),
        app_commands.Choice(name = "Fast", value = "fast"),
        app_commands.Choice(name = "Slow", value = "slow")
    ]
)
@app_commands.checks.has_role("Dungeon Master")
async def travel(interaction: discord.Interaction, weather: str, forecast: str, start_hex: str, target_hex: str, pace: str, nav_check: int):
    '''
    Attempt to travel to a new location hex in Chult.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    weather : str
        What is the weather like?
    forecast : str
        What is the weather forecast for later today?
    start_hex : str
        Where is the party?
    target_hex : str
        Where is the party trying to go?
    pace : str
        What is the traveling pace?
    nav_check : int
        What was the result of the navigator's survival check?
    '''
    #Load templates
    with open(templates_dir.joinpath('travel_start.md'), encoding='utf8') as template_file:
        travel_template = template_file.read()

    # Generate and send the start of the travel log.
    travel_start_log = travel_template.format(
        start_hex = start_hex.capitalize(),
        weather = weather,
        pace = pace
    )
    await interaction.response.send_message(travel_start_log)

    navigate_result = ""

    # Set DC for navigation check based on starting hex location.
    if start_hex == "town" or start_hex == "fort" or start_hex == "camp":
        start_dc = 10
    elif start_hex == "road" or start_hex == "coast" or start_hex == "lake":
        start_dc = 10
    elif start_hex == "jungle" or start_hex == "river":
        start_dc = 15
    elif start_hex == "mountains" or start_hex == "swamp" or start_hex == "wasteland":
        start_dc = 20
    else:
        start_dc = 10

    # Modify the DC based on the pace.
    if pace == "fast":
        start_dc += 5
    elif pace == "slow":
        start_dc -= 5

        # For slow pace, roll 1d4 to see if the party fails to make progress.
        slow_roll = random.randint(1, 4)
        if slow_roll == 1:
            navigate_result = "You fail to make any progress!"
            end_hex = start_hex

    # Check if the party made progress.
    if navigate_result != "You fail to make any progress!":
        # Check if the navigator passed the navigation check.
        if nav_check >= start_dc:
            navigate_result = "You successfully navigate to the new hex!"
            end_hex = target_hex
        else:
            navigate_result = "The party has become lost!"

            # Create a select menu asking the DM for a new ending hex location.
            options_location = [
                discord.SelectOption(label='Town', emoji=f'{chr(127960)}{chr(65039)}'),
                discord.SelectOption(label='Fort', emoji=f'{chr(127984)}'),
                discord.SelectOption(label='Camp', emoji=f'{chr(127957)}{chr(65039)}'),
                discord.SelectOption(label='Road', emoji=f'{chr(128739)}{chr(65039)}'),
                discord.SelectOption(label='Coast', emoji=f'{chr(127958)}{chr(65039)}'),
                discord.SelectOption(label='Lake', emoji=f'{chr(127754)}'),
                discord.SelectOption(label='Jungle', emoji=f'{chr(127796)}'),
                discord.SelectOption(label='River', emoji=f'{chr(127966)}{chr(65039)}'),
                discord.SelectOption(label='Mountain', emoji=f'{chr(9968)}{chr(65039)}'),
                discord.SelectOption(label='Swamp', emoji=f'{chr(129439)}'),
                discord.SelectOption(label='Wasteland', emoji=f'{chr(127964)}{chr(65039)}'),
            ]

            # Create the location view
            view = discord_views.SelectMenu(interaction.user, options_location, "Select their unintended destination...")
            await interaction.followup.send("The party became lost!",view=view, ephemeral=True)
            end_hex = await view.wait_for_selection()

    # Set DC for survival points check based on ending hex location.
    if end_hex == "town" or end_hex == "fort" or end_hex == "camp":
        end_dc = 10
    elif end_hex == "road" or end_hex == "coast" or end_hex == "lake":
        end_dc = 10
    elif end_hex == "jungle" or end_hex == "river":
        end_dc = 15
    elif end_hex == "mountains" or end_hex == "swamp" or end_hex == "wasteland":
        end_dc = 20
    else:
        end_dc = 10

    # Calculate any available survival points.
    survival_points = nav_check - end_dc
    survival_points = max(survival_points, 0)

    # Generate and send the end of the travel log.
    with open(templates_dir.joinpath('travel_result.md'), encoding='utf8') as template_file:
        travel_template = template_file.read()

    travel_result_log = travel_template.format(
        navigate_result = navigate_result,
        end_hex = end_hex.capitalize(),
        forecast = forecast,
        survival_points = survival_points
    )
    await interaction.followup.send(travel_result_log)

# Bot command to end the Chultan day.
@tree.command(
    name = "rest",
    description = "End the day in Chult.",
    guilds = guild_objs
)
@app_commands.describe(
    day = "Which day are we on?",
    location = "Where are we?",
    weather = "What is the weather like?",
    status = "What is the party's status?"
)
@app_commands.choices(
    weather = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ]
)
@app_commands.checks.has_role("Dungeon Master")
async def rest(interaction: discord.Interaction, day: int, location: str, weather: str, status: str):
    """
    End the day in Chult.

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
    status : str
        What is the party's status?
    """

    #Load templates
    with open(templates_dir.joinpath('rest.md'), encoding='utf8') as template_file:
        rest_template = template_file.read()

    # Generate the starting log Markdown
    rest_log = rest_template.format(
        day = day,
        location = location,
        weather = weather,
        status = status
    )

    await interaction.response.send_message(rest_log)

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
