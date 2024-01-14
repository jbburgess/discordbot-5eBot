# discordbot-5eBot
5eBot is a Discord bot for retrieving information related to D&D 5e.

## Requirements
The backend data required to populate responses is not included in this repository. In order to function, the bot requires the following:
* A `/data` directory containing JSON data in the same structure and format as those seen in the `/data` directory of a 5e.tools mirror.
* A `config.json` file in the main directory containing a `discord.token` element with the token of your registered Discord application.
* Required Python packages for the runtime environment are detailed in `requirements.txt`. Pip is required to install these dependencies.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss the potential change. If adding additional command support for the bot, please follow the structure below and make sure to update any related tests as needed. 

### Project Structure
The main bot definition and execution happens in `main.py` in the root directory.

#### Modules
The `/modules` directory contains Python classes used for structuring data and behaviors related to certain types of D&D information (e.g., a spell or an item). The main bot imports these and initializes instances of these classes to process related bot commands.

#### Templates
The `/templates` directory contains Markdown templates used to format bot responses in Discord. If you'd like to change the Markdown formatting for how the bot responds to certain commands, you would find that here.
