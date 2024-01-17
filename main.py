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
    description = "Generate a new day in Chult, continue an expedition, log everything at the end.",
    guilds = guild_objs
)
@app_commands.describe(day = "Which day are we on?")
#async def roll(interaction: discord.Interaction, day: int):
async def select_menu(interaction: discord.Interaction, day: int):
    """
    Generate a new day in Chult, continue an expedition, log everything at the end.
    """
    
    #Load templates
    templates_dir = Path(root_dir, TEMPLATESDIR)
    with open(templates_dir.joinpath('startday-base.md'), encoding='utf8') as template_file:
                startday_base = template_file.read()
    with open(templates_dir.joinpath('startday-travel.md'), encoding='utf8') as template_file:
                startday_travel = template_file.read()
    
    # Initialize the main answers dict to gather all the answers from this interaction
    answers = {}

    # Send a modal as an initial response to collect any misc notes
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

    # If the user entered any notes, format and add them to the answers dict
    if inputted_notes != "":
        inputted_notes = f"Additional Notes: {inputted_notes}"
    answers['notes'] = inputted_notes

    # Build and send any select menus in the JSON config, storing the result in the answers dictionary    
    selectmenu_data = config['newday']['selectmenu']

    # Loop through configured select menus
    for entry in selectmenu_data:
        logger.debug('Processing select menu: %s', entry['id'])
        
        # Check whether the select menu has a configured condition for displaying it
        if 'condition' in entry:
            condition_key = entry['condition']['key']
            condition_value = entry['condition']['value']
            condition_bool = entry['condition']['bool']

            #If the configured condition is not met, skip this select menu
            if condition_key in answers:
                if condition_bool:
                    if answers[condition_key] != condition_value:
                        continue
                else:
                    if answers[condition_key] == condition_value:
                        continue

        # Create the menu options for this select menu
        options = []

        for option in entry['options']:
            emoji_codes = option['emoji']
            emoji = ''.join([chr(int(code)) for code in emoji_codes])

            if 'description' in option:
                options.append(discord.SelectOption(label = option['label'], description = option['description'], emoji = emoji))
            else:
                options.append(discord.SelectOption(label = option['label'], emoji = emoji))

        # Create the select menu view and wait for a selection
        view = discord_views.SelectMenu(interaction.user, options, entry['placeholder'])
        await interaction.followup.send(view=view, ephemeral=True)
        selection = await view.wait_for_selection()
        answers[entry['id']] = selection

        # Create any drill-down select menu views configured for the selected option
        selected_option = next((option for option in entry['options'] if option['label'] == selection), None)
        
        if 'submenu' in selected_option:
            submenu_data = selected_option['submenu']

            for submenu_entry in submenu_data:
                options = []

                for option in submenu_entry['options']:
                    emoji_codes = option['emoji']
                    emoji = ''.join([chr(int(code)) for code in emoji_codes])

                    if 'description' in option:
                        options.append(discord.SelectOption(label = option['label'], description = option['description'], emoji = emoji))
                    else:
                        options.append(discord.SelectOption(label = option['label'], emoji = emoji))

                view = discord_views.SelectMenu(interaction.user, options, submenu_entry['placeholder'])
                await interaction.followup.send(view=view, ephemeral=True)
                answers[submenu_entry['id']] = await view.wait_for_selection()

    if answers['location'] != "Port Nyanzaru":
        # Generate the travel part of the template Markdown
        template_travel = startday_travel.format(
            enoughfood = answers['enoughfood'],
            enoughwater = answers['enoughwater'],
            enoughspray = answers['enoughspray']
        )
    else:
        template_travel = ""
    
    # Generate the starting log Markdown
    starting_log = startday_base.format(
        day = day,
        location = answers['location'],
        weather = answers['weather'],
        template_travel = template_travel,
        notes = answers['notes']
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
