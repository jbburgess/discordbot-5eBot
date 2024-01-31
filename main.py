'''
A Discord bot for looking up information related to D&D 5th Edition.

Currently only supports rolling dice in NdN format (e.g., 1d20, 2d4...).

Functions:
    roll(dice: str) -> str
'''

# Importing required modules
import argparse
import glob
import json
import logging
from pathlib import Path
import random
import re
import time
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
journal_channelids = [int(id) for id in config['discord']['channelids']['journal']]

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
    name = "day",
    description = "Log a day in Chult.",
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
async def day(interaction: discord.Interaction, day: int, location: str, weather: str, forecast: str, status: str):
    """
    Log a day in Chult.

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
    with open(templates_dir.joinpath('day.md'), encoding='utf8') as template_file:
        day_template = template_file.read()

    # Generate the starting log Markdown
    day_log = day_template.format(
        day = day,
        location = location,
        weather = weather,
        status = status
    )

    await interaction.response.send_message(day_log)
    await interaction.followup.send(f'Forecast: {forecast}', ephemeral = True)

# Bot command to ask party to react to the checklist.
@tree.command(
    name = "checklist",
    description = "Prompt the party to complete the checklist for the day.",
    guilds = guild_objs
)
@app_commands.describe(
    day = "Which day are we on?"
)
@app_commands.checks.has_role("Dungeon Master")
async def checklist(interaction: discord.Interaction, day: int):
    '''
    Prompt the party to complete the checklist for the day.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    day : int
        Which day are we on?
    '''
    #Load templates
    checklist_templates = glob.glob(f'{Path(templates_dir, "checklist_*.md")}')
    for file in checklist_templates:
        with open(file, encoding='utf8') as template_file:
            markdown = template_file.read()

        if file == checklist_templates[0]:
            checklist_header = markdown.format(
                day = day
            )
            await interaction.response.send_message(checklist_header)
        else:
            await interaction.followup.send(markdown)

# Bot command to attempt to travel to a different hex.
@tree.command(
    name = "travel",
    description = "Attempt to travel to a new location hex in Chult.",
    guilds = guild_objs
)
@app_commands.describe(
    day = "Which day are we on?",
    weather = "What is the weather like?",
    forecast = "What is the weather forecast for later today?",
    start_hex = "Where is the party?",
    target_hex = "Where is the party trying to go?",
    pace = "What is the traveling pace?",
    nav_check = "What was the result of the navigator's survival check?",
    encounter = "What does the party encounter during their travel?"
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
        app_commands.Choice(name = "Port Nyanzaru", value = ":houses: Port Nyanzaru"),
        app_commands.Choice(name = "Fort Beluarian", value = ":castle: Fort Beluarian"),
        app_commands.Choice(name = "Sea", value = ":sailboat: Sea"),
        app_commands.Choice(name = "Mine", value = ":pick: Mine"),
        app_commands.Choice(name = "Coast", value = ":beach: Coast"),
        app_commands.Choice(name = "Lake", value = ":fish: Lake"),
        app_commands.Choice(name = "Jungle", value = ":palm_tree: Jungle"),
        app_commands.Choice(name = "River", value = ":canoe: River"),
        app_commands.Choice(name = "Mountains", value = ":mountain: Mountains"),
        app_commands.Choice(name = "Swamp", value = ":mosquito: Swamp"),
        app_commands.Choice(name = "Wasteland", value = ":desert: Wasteland")
    ],
    target_hex = [
        app_commands.Choice(name = "Port Nyanzaru", value = ":houses: Port Nyanzaru"),
        app_commands.Choice(name = "Fort Beluarian", value = ":castle: Fort Beluarian"),
        app_commands.Choice(name = "Sea", value = ":sailboat: Sea"),
        app_commands.Choice(name = "Mine", value = ":pick: Mine"),
        app_commands.Choice(name = "Coast", value = ":beach: Coast"),
        app_commands.Choice(name = "Lake", value = ":fish: Lake"),
        app_commands.Choice(name = "Jungle", value = ":palm_tree: Jungle"),
        app_commands.Choice(name = "River", value = ":canoe: River"),
        app_commands.Choice(name = "Mountains", value = ":mountain: Mountains"),
        app_commands.Choice(name = "Swamp", value = ":mosquito: Swamp"),
        app_commands.Choice(name = "Wasteland", value = ":desert: Wasteland"),
        app_commands.Choice(name = "N/A", value = "N/A")
    ],
    pace = [
        app_commands.Choice(name = "Normal", value = "normal"),
        app_commands.Choice(name = "Fast", value = "fast"),
        app_commands.Choice(name = "Cautious", value = "cautious")
    ]
)
@app_commands.checks.has_role("Dungeon Master")
async def travel(interaction: discord.Interaction, day: int, weather: str, forecast: str, start_hex: str, target_hex: str, pace: str, nav_check: int, encounter: typing.Optional[str] = None):
    '''
    Attempt to travel to a new location hex in Chult.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    day : int
        Which day are we on?
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
    encounter : str, optional
        What does the party encounter during their travel?
    '''
    #Load templates
    with open(templates_dir.joinpath('travel_start.md'), encoding='utf8') as template_file:
        travel_template = template_file.read()

    # Generate and send the start of the travel log.
    travel_start_log = travel_template.format(
        day = day,
        start_hex = start_hex,
        weather = weather,
        pace = pace
    )
    await interaction.response.send_message(travel_start_log)

    # Build suspense...
    time.sleep(5.0)

    navigate_result = ""

    # Set DC for navigation check based on starting hex location.
    if start_hex in [":houses: Port Nyanzaru", ":castle: Fort Beluarian", ":sailboat: Sea", ":pick: Mine"]:
        start_dc = 0
    elif start_hex in [":beach: Coast", ":fish: Lake"]:
        start_dc = 10
    elif start_hex in [":palm_tree: Jungle", ":canoe: River"]:
        start_dc = 15
    elif start_hex in [":mountain: Mountains", ":mosquito: Swamp", ":desert: Wasteland"]:
        start_dc = 20
    else:
        start_dc = 10

    # Modify the DC based on the pace.
    if pace == "fast":
        start_dc += 5
    elif pace == "cautious":
        start_dc -= 5

        # For slow pace, roll 1d4 to see if the party fails to make progress.
        slow_roll = random.randint(1, 4)
        if slow_roll == 1:
            navigate_result = ":confounded: The Castaways become mired in the wilderness and fail to leave their current hex."
            end_hex = start_hex

    # Check if the party made progress.
    if navigate_result != ":confounded: The Castaways become mired in the wilderness and fail to leave their current hex.":
        # Check if the navigator passed the navigation check.
        if nav_check >= start_dc:
            navigate_result = ":partying_face: Success! The Castaways proceed toward their destination."
            end_hex = target_hex
        else:
            navigate_result = ":scream: The Castaways become lost and do not end up where they intended!"

            # Create a select menu asking the DM for a new ending hex location.
            options_location = [
                discord.SelectOption(label='Port Nyanzaru', emoji=f'{chr(127960)}{chr(65039)}', value = ":houses: Port Nyanzaru"),
                discord.SelectOption(label='Fort Beluarian', emoji=f'{chr(127984)}', value = ":castle: Fort Beluarian"),
                discord.SelectOption(label='Sea', emoji=f'{chr(9973)}', value = ":sailboat: Sea"),
                discord.SelectOption(label='Mine', emoji=f'{chr(9935)}{chr(65039)}', value = ":pick: Mine"),
                discord.SelectOption(label='Coast', emoji=f'{chr(127958)}{chr(65039)}', value = ":beach: Coast"),
                discord.SelectOption(label='Lake', emoji=f'{chr(128031)}', value = ":fish: Lake"),
                discord.SelectOption(label='Jungle', emoji=f'{chr(127796)}', value = ":palm_tree: Jungle"),
                discord.SelectOption(label='River', emoji=f'{chr(128758)}', value = ":canoe: River"),
                discord.SelectOption(label='Mountain', emoji=f'{chr(9968)}{chr(65039)}', value = ":mountain: Mountains"),
                discord.SelectOption(label='Swamp', emoji=f'{chr(129439)}', value = ":mosquito: Swamp"),
                discord.SelectOption(label='Wasteland', emoji=f'{chr(127964)}{chr(65039)}', value = ":desert: Wasteland")
            ]

            # Create the location view
            view = discord_views.SelectMenu(interaction.user, options_location, "Select their unintended destination...")
            await interaction.followup.send("The party became lost!",view=view, ephemeral=True)
            end_hex = await view.wait_for_selection()

    # Set DC for survival points check based on ending hex location.
    if end_hex in [":houses: Port Nyanzaru", ":castle: Fort Beluarian", ":sailboat: Sea", ":pick: Mine"]:
        end_dc = 0
    elif end_hex in [":beach: Coast", ":fish: Lake"]:
        end_dc = 10
    elif end_hex in [":palm_tree: Jungle", ":canoe: River"]:
        end_dc = 15
    elif end_hex in [":mountain: Mountains", ":mosquito: Swamp", ":desert: Wasteland"]:
        end_dc = 20
    else:
        end_dc = 10

    # Calculate any available survival points.
    survival_points = nav_check - end_dc
    survival_points = max(survival_points, 0)
    if survival_points == 0:
        survival_points = "None"
    if end_dc == 0:
        survival_points = "N/A"

    # Generate and send the end of the travel log.
    if encounter is None:
        with open(templates_dir.joinpath('travel_result.md'), encoding='utf8') as template_file:
            travel_template = template_file.read()

        travel_result_log = travel_template.format(
            navigate_result = navigate_result,
            end_hex = end_hex,
            forecast = forecast,
            survival_points = survival_points
        )
    else:
        with open(templates_dir.joinpath('travel_result_encounter.md'), encoding='utf8') as template_file:
            travel_template = template_file.read()

        travel_result_log = travel_template.format(
            navigate_result = navigate_result,
            encounter = encounter,
            end_hex = end_hex,
            forecast = forecast,
            survival_points = survival_points
        )

    await interaction.followup.send(travel_result_log)

# Bot command to report a standalone encounter.
@tree.command(
    name = "encounter",
    description = "Report an encounter.",
    guilds = guild_objs
)
@app_commands.describe(
    header_emoji = "An emoji to represent this encounter.",
    day = "Which day are we on?",
    time = "What time of day did the encounter occur?",
    location = "Where is the party?",
    weather = "What is the weather like?",
    notes = "Any notes on the encounter?"
)
@app_commands.choices(
    weather = [
        app_commands.Choice(name = "Normal", value = ":white_sun_cloud: Normal"),
        app_commands.Choice(name = "Deluge", value = ":thunder_cloud_rain: Deluge"),
        app_commands.Choice(name = "Sweltering", value = ":sun: Sweltering")
    ]
)
@app_commands.checks.has_role("Dungeon Master")
async def encounter(interaction: discord.Interaction, header_emoji: str, day: int, time: str, location: str, weather: str, notes: str):
    """
    Report an encounter.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    header_emoji : str
        An emoji to represent this encounter.
    day : int
        Which day are we on?
    time : int
        What time of day did the encounter occur?
    location : str
        Where is the party?
    weather : int
        What is the weather like?
    notes : str
        Any notes on the encounter?
    """

    #Load templates
    with open(templates_dir.joinpath('encounter.md'), encoding='utf8') as template_file:
        encounter_template = template_file.read()

    # Generate the starting log Markdown
    encounter_log = encounter_template.format(
        header_emoji = header_emoji,
        day = day,
        time = time,
        location = location,
        weather = weather,
        notes = notes
    )

    await interaction.response.send_message(encounter_log)

# Bot command to start a new Chultan day.
@tree.command(
    name = "entry",
    description = "Add a general log entry to the journal.",
    guilds = guild_objs
)
@app_commands.describe(
    header_emoji = "An emoji to represent this entry.",
    day = "Which day are we on?",
    notes = "Notes for this log entry."
)
@app_commands.checks.has_role("Dungeon Master")
async def entry(interaction: discord.Interaction, header_emoji: str, day: int, notes: str):
    """
    Log a day in Chult.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object.
    header_emoji : str
        An emoji to represent this entry.
    day : int
        Which day are we on?
    notes : str
        Notes for this log entry.
    """

    #Load templates
    with open(templates_dir.joinpath('entry.md'), encoding='utf8') as template_file:
        entry_template = template_file.read()

    # Generate the starting log Markdown
    entry_log = entry_template.format(
        header_emoji = header_emoji,
        day = day,
        notes = notes
    )

    await interaction.response.send_message(entry_log)

# Bot command to take a rest.
@tree.command(
    name = "rest",
    description = "Settle down for a rest in Chult.",
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
    Settle down for a rest in Chult.

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

# React to messages that are sent
@bot.event
async def on_message(message):
    '''React to messages that are sent'''
    logger.debug('Reacting to message...')
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        logger.debug('Message sent by bot, ignoring...')
        return

    if message.channel.id in journal_channelids and message.author != bot.user and message.reference:
        if message.reference.resolved and message.reference.resolved.author == bot.user:
            logger.debug('Reply to bot message detected, adding note...')
            user = message.author.mention
            note = message.content
            orig_message = await message.channel.fetch_message(message.reference.message_id)

            # If the note is a command to clear a user's personal notes.
            if note == ('!clear'):
                logger.debug('Clearing personal notes for %s...', user)
                lines = orig_message.content.split('\n')
                new_content = ''
                for line in lines:
                    if user not in line or 'Personal Note' not in line:
                        new_content += line + '\n'
            # If the note is a command from the DM to clear all personal notes, clear all personal notes.
            elif note == ('!clearall'):
                logger.debug('User roles: %s', message.author.roles)
                dmrole_pattern = r'<Role id=[0-9]{19} name=\'Dungeon Master\'>'

                if any(role.name == 'Dungeon Master' for role in message.author.roles):
                    logger.debug('Clearing ALL personal notes...')
                    lines = orig_message.content.split('\n')
                    new_content = ''
                    for line in lines:
                        if 'Personal Note' not in line:
                            new_content += line + '\n'
                else:
                    logger.debug('User is not a DM, ignoring...')
                    await message.delete()
                    return
            # Otherwise, add the note to the original message.
            else:
                logger.debug('Adding personal note for %s...', user)
                append = f'> **Personal Note {user}**  {note}'
                new_content = orig_message.content
                new_content += f'\n{append}'

            await orig_message.edit(content = new_content)
            await message.delete()
    elif message.channel.id not in journal_channelids:
        logger.debug('Message not sent in journal channel, ignoring... (Sent in ID: %s)', message.channel.id)
    elif message.author == bot.user:
        logger.debug('Message sent by bot, ignoring...')
    elif not message.reference:
        logger.debug('Message not a reply, ignoring...')

# When reactions are added to messages
@bot.event
async def on_reaction_add(reaction, user):
    '''When reactions are added to messages'''
    logger.debug('Reacting to reaction...')
    message = reaction.message
    content = message.content

    # Ignore reactions on messages not sent by the bot itself
    if message.author != bot.user:
        logger.debug('Reaction not on a message sent by bot, ignoring...')
        return

    # Check if reaction is on a checklist question.
    if message.channel.id in journal_channelids and "today?)*" in content:
        if reaction.emoji in (f'{chr(9989)}', f'{chr(10060)}'): # Checkmark or X emoji only
            async for user in reaction.users():
                append = f'> {reaction.emoji} {user.display_name}'
                current_content = message.content
                current_content += f'\n{append}'

                # Append reaction to original checklist message and remove reaction.
                await message.edit(content = current_content)
                await reaction.remove(user)
        else:
            logger.debug('Reaction is not a check or X... (Emoji: %s)', reaction.emoji)
            await reaction.remove(user)
    else:
        logger.debug('Reaction not on a checklist question, ignoring... (Message: %s)', message.content)

# Running bot with token
bot.run(TOKEN)
