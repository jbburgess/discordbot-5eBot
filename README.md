# discordbot-5eBot
5eBot is a Discord bot for looking up information related to D&D 5e. It currently offers two slash commands, `/roll` and `/spell`:
* `/roll`:  Roll a set of dice and add an optional modifier if desired.
    * Inputs: `dice` *(required)* in 'NdN' format (e.g., 1d20, 2d4...); `modifier` *(optional)* in '[\+/-]N' format.
* `/spell`:  Look up a D&D 5e spell by name. Works for just about any source book, but a single book can be specified to narrow the search.
    * Inputs: `name` *(required)*, must be an exact match for now; `source` *(optional)* in abbreviated format (e.g., PHB, TCE).

## Requirements
The backend data required to populate responses is not included in this repository. In order to function, the bot requires the following:
* A `/data` directory containing JSON data in the same structure and format as those seen in the `/data` directory of a 5e.tools mirror. Currently only the `/spells` subdirectory is used, but other data will be used as more commands are added.
* The token for your valid Discord application populated in the `discord.token` element of the `config.json` file in the root directory.
* Required Python packages for the runtime environment are detailed in `requirements.txt`. Pip is required to install these dependencies.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss the potential change. If adding additional command support for the bot, please follow the structure below and make sure to update any related tests as needed. 

### Project Structure
The bot definition and execution happens in `main.py` in the root directory.

#### Modules
The `/modules` directory contains Python classes used for structuring data and behaviors related to certain types of D&D information (e.g., a spell or an item). The main bot imports these and initializes instances of these classes to process related bot commands.

#### Templates
The `/templates` directory contains Markdown templates used to format bot responses in Discord. This is where to change the Markdown formatting for messages the bot sends in response to certain commands.