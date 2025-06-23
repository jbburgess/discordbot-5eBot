# discordbot-5eBot

5eBot is a Discord bot for looking up information related to D&D 5e, heavily customized for use in a Tomb of Annihilation campaign. It currently offers the following slash commands:

* `/roll`: Roll a set of dice and add an optional modifier if desired.
  * Inputs: `dice` *(required)* in 'NdN' format (e.g., 1d20, 2d4...); `modifier` *(optional)* in '[+/-]N' format.
  * Access: All users
* `/spell`: Look up a D&D 5e spell by name. Works for just about any source book, but a single book can be specified to narrow the search.
  * Inputs: `name` *(required)*, must be an exact match for now; `source` *(optional)* in abbreviated format (e.g., PHB, TCE).
  * Access: All users
* `/day`: Log a day in Chult for the Tomb of Annihilation campaign and post a formatted log to Discord.
  * Inputs: `day` *(required)*, integer; `location`, `weather`, `forecast`, `status` *(all required)*, dropdown selection.
  * Access: Dungeon Master only
* `/checklist`: Prompt the party to complete the checklist for the day.
  * Inputs: `day` *(required)*, integer.
  * Access: Dungeon Master only
* `/travel`: Attempt to travel to a new location hex in Chult, logging the journey and results.
  * Inputs: `day`, `weather`, `forecast`, `start_hex`, `target_hex`, `pace`, `nav_check` *(all required)*, dropdown selection; `encounter` *(optional)*, dropdown selection.
  * Access: Dungeon Master only
* `/encounter`: Report a standalone encounter and post a formatted log to Discord.
  * Inputs: `header_emoji`, `day`, `time`, `location`, `weather`, `notes` *(all required)*, dropdown selection.
  * Access: Dungeon Master only
* `/entry`: Add a general log entry to the journal.
  * Inputs: `header_emoji`, `day`, `notes` *(all required)*, dropdown selection.
  * Access: Dungeon Master only
* `/rest`: Settle down for a rest in Chult and post a formatted log to Discord.
  * Inputs: `day`, `location`, `weather`, `status` *(all required)*, dropdown selection.
  * Access: Dungeon Master only

> [!NOTE]
> Some commands (indicated above) are only available to the DM. To see the commands and use them, a user must have the `Dungeon Master` role assigned in the Discord server.

In addition to slash commands, the bot also has an LLM-powered chatbot functionality for natural language chatting in Discord.

* To reduce unneccessary token use and vector storage, the bot only responds if it is @mentioned or replied to in a configured Discord channel.
* The included system message defines the bot's personality as an in-game character that the adventuring party can interact with; this can be customized as desired.
* A memory layer is integrated as well, allowing the chatbot to learn about the adventuring characters and form long-term memories over time as they interact with it via Discord.
    * Short-term memory - If there are multiples replies chained together in an ongoing conversation, the bot will receive the entire context of that reply chain, enabling back-and-forth conversation.
    * Long-term memory - The bot will process and extract relevant information from all interactions with it in Discord, storing user-specific memories about personal details, preferences, interactions, experiences, relationships, interests, etc.

## Requirements

The backend data required to populate responses is not included in this repository. In order to function, the bot requires the following:

* A `/data` directory containing JSON data in the same structure and format as those seen in the `/data` directory of a 5e.tools mirror. Currently only the `/spells` subdirectory is used, but other data will be used as more commands are added.
* The token for your valid Discord application populated in the `discord.token` element of the `config.json` file in the root directory, along with any test and prod guild IDs.
* Required Python packages for the runtime environment are detailed in `requirements.txt`. Pip is required to install these dependencies.
* For LLM chat:
  * An API endpoint and key for a deployed LLM to sends prompts to and receive completions from.
* For memory layer:
  * An API endpoint and key for a deployed embeddings model, to generate embeddings for stored memories.
  * An index store and API key storing and searching memories

The current configuration assumes an OpenAI model deployed via Azure OpenAI Service and vector storage via Azure AI Search.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss the potential change. If adding additional command support for the bot, please follow the structure below and make sure to update any related tests as needed.

### Project Structure

* `main.py`: The main entry point for the bot. Contains all Discord event handlers, slash command definitions, and the core logic for interacting with Discord and Azure OpenAI.
* `config.json`: Configuration file containing Discord tokens, guild IDs, Azure OpenAI credentials, and other environment settings.
* `requirements.txt`: Lists all required Python packages for running the bot.
* `/modules/`: Contains Python modules for specific bot features and data types, such as:
  * `spells.py`: Logic for spell lookup and formatting.
  * `discord_views.py`: Custom Discord UI components (e.g., select menus).
* `/templates/`: Markdown templates used to format bot responses for various commands (e.g., day logs, checklists, encounters).
* `/tests/`: Contains test scripts for validating bot functionality.

#### How It Works

* The bot loads configuration from `config.json` and initializes Discord and Azure OpenAI clients.
* Slash commands are defined in `main.py` using the Discord app commands API.
* When a command is invoked, the bot processes the input, loads any necessary templates, and sends formatted responses to Discord.
* The bot also supports LLM-powered chat outside of slash commands when @mentioned or replied to, using Azure OpenAI for natural language responses and a memory layer for long-running context.
