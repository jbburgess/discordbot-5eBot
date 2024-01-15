import json
import logging
from pathlib import Path
import re
import string

# Initialize logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

stderr_log_handler = logging.StreamHandler()
file_log_handler = logging.FileHandler('logfile.log')

stderr_log_handler.setLevel(logging.DEBUG)
file_log_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_log_handler.setFormatter(formatter)
file_log_handler.setFormatter(formatter)

logger.addHandler(stderr_log_handler)
logger.addHandler(file_log_handler)

# Class for looking up spells
class Spell:
    '''
    Class for looking up D&D 5e spells from local JSON data.

    Attributes
    ----------
    name : str
        The name of the spell.
    classes : list
        The classes that can use the spell.
    source : str
        The source of the spell.
    '''
    # Initialize class attributes
    root_dir = Path(Path(Path(__file__).parent).parent)
    spells_dir = Path(root_dir, 'data/spells')
    templates_dir = Path(root_dir, 'templates')

    logger.info('Root directory: %s', root_dir)
    logger.info('Spells directory: %s', spells_dir)
    logger.info('Templates directory: %s', templates_dir)

    # Load spell sources and index from JSON file
    with open(spells_dir.joinpath('sources.json'), encoding='utf8') as json_file:
        spells_sources = json.load(json_file)
    with open(spells_dir.joinpath('index.json'), encoding='utf8') as json_file:
        spells_index = json.load(json_file)

    # Initialize class instance
    def __init__(self, name: str, source: str=None):
        '''
        Initialize the spell class instance.
        
        Parameters
        ----------
        name : str
            The name of the spell.
        source : str
            The source book of the spell.
        '''
        self.name = string.capwords(name)
        if source is not None:
            self.source = source.upper()
        else:
            self.source = None

        logger.debug('Provided name: %s', self.name)
        logger.debug('Provided source: %s', self.source)

        # Retrieve filename of source book containing the spell
        self.source_file = self._get_source_file()
        logger.info('Source file: %s', self.source_file)

        # Retrieve the spell information from the source book
        self.spell_dict = None
        if self.source_file is not None:
            self.spell_dict = self._get_spell()
            logger.info('Spell dict: %s', self.spell_dict)

        # Set spell attributes
        if self.spell_dict is not None:
            self.spell_name = self.spell_dict['name']

            # Format spell level string, accounting for cantrips
            self.spell_level = self.spell_dict['level']
            if self.spell_level == 0:
                self.spell_level = 'Cantrip'

            # Format spell school string, accounting for shortened school names
            school_switcher = {
                'A': 'Abjuration',
                'C': 'Conjuration',
                'D': 'Divination',
                'E': 'Enchantment',
                'I': 'Illusion',
                'N': 'Necromancy',
                'T': 'Transmutation'
            }
            self.spell_school = school_switcher.get(self.spell_dict['school'], 'Unknown')

            # Call functions for more complex spell attributes
            self.spell_casting_time = self._format_spell_casting_time()
            self.spell_range = self._format_spell_range()
            self.spell_components = self._format_spell_components()
            self.spell_duration = self._format_spell_duration()
            self.spell_description = self._format_spell_description()
            self.spell_description = self._remove_description_decorators()

            self.source_book = self.spell_dict['source']
            self.source_page = self.spell_dict['page']

            if 'otherSources' in self.spell_dict.keys():
                self.sources_other = ". Also found in "
                self.sources_other += "; ".join(f'{source["source"]}, page {source["page"]}' for source in self.spell_dict['otherSources'])
            else:
                self.sources_other = ""

            # Retrieve base spell markdown template and enumerate generated strings.
            with open(self.templates_dir.joinpath('spell-base.md'), encoding='utf8') as template_file:
                self.spell_template = template_file.read()
            self.spell_markdown = self.spell_template.format(
                spell_name = self.spell_name,
                spell_level = self.spell_level,
                spell_school = self.spell_school,
                spell_casting_time = self.spell_casting_time,
                spell_range = self.spell_range,
                spell_components = self.spell_components,
                spell_duration = self.spell_duration,
                spell_description = self.spell_description,
                source_book = self.source_book,
                source_page = self.source_page,
                sources_other = self.sources_other
            )

            logger.debug('Spell markdown: %s', self.spell_markdown)
            logger.debug('Spell markdown length: %s', len(self.spell_markdown))

    def __repr__(self) -> str:
        '''
        Returns
        -------
        str
            The detailed string representation, containing information needed to recreate the object.
        '''
        class_name = type(self).__name__
        return f'{class_name}(name={self.name!r}, source={self.source!r})'

    def __str__(self):
        '''
        Returns
        -------
        str
            The friendly string representation of the spell.
        '''
        return f'{self.name}'

    def _get_source_file(self) -> str:
        '''
        Function to retrieve the source book of a spell.

        Returns
        -------
        str
            The filename of the source book containing the spell.
        '''
        logger.debug('Searching for source file for spell %s.', self.name)
        # Find and return the filename of the source book containing the spell
        if self.source is None:
            logger.debug('Source is None, searching for spell in all sources.')
            for key, value in self.spells_sources.items():
                if isinstance(value, dict):
                    if self.name in value:
                        return self.spells_index[key]
        elif self.source in self.spells_index:
            logger.debug('Source found in index, returning source file.')
            return self.spells_index[self.source]
        else:
            return None

    def _get_spell(self) -> dict:
        '''
        Function to retrieve spell information from the JSON source file.

        Returns
        -------
        dict
            Dictionary object containing the spell information.
        '''

        # Retrieve source book for spell.
        with open(self.spells_dir.joinpath(self.source_file), encoding='utf8') as json_file:
            source_spells = json.load(json_file)

        # Retrieve spell from source book.
        for entry in source_spells['spell']:
            if entry['name'] == self.name:
                return entry
        return None

    def _format_spell_casting_time(self) -> str:
        '''
        Function to format the spell casting time string.

        Returns
        -------
        str
            A friendly string for the spell casting time.
        '''
        if len(self.spell_dict['time']) == 1:
            spell_casting_time = f'{self.spell_dict["time"][0]["number"]} {self.spell_dict["time"][0]["unit"]}'
        else:
            for i in range(len(self.spell_dict['time'])):
                if i == 0:
                    spell_casting_time = f'{self.spell_dict["time"][i]["number"]} {self.spell_dict["time"][i]["unit"]}'
                    if 'condition' in self.spell_dict["time"][i].keys():
                        spell_casting_time += f' {self.spell_dict["time"][i]["condition"]}'
                elif i == len(self.spell_dict['time']) - 1:
                    spell_casting_time += f'; or {self.spell_dict["time"][i]["number"]} {self.spell_dict["time"][i]["unit"]}'
                    if 'condition' in self.spell_dict["time"][i].keys():
                        spell_casting_time += f' {self.spell_dict["time"][i]["condition"]}'
                else:
                    spell_casting_time += f'; {self.spell_dict["time"][i]["number"]} {self.spell_dict["time"][i]["unit"]}'
                    if 'condition' in self.spell_dict["time"][i].keys():
                        spell_casting_time += f' {self.spell_dict["time"][i]["condition"]}'

        return spell_casting_time

    def _format_spell_range(self) -> str:
        '''
        Function to format the spell range string.

        Returns
        -------
        str
            A friendly string for the spell range.
        '''
        # Format spell range string, accounting for type of range
        if 'type' in self.spell_dict['range'].keys():
            if self.spell_dict['range']['type'] == 'point':
                if self.spell_dict['range']['distance']['type'] in ['feet', 'mile', 'miles']:
                    spell_range = f'{self.spell_dict["range"]["distance"]["amount"]} {self.spell_dict["range"]["distance"]["type"]}'
                else:
                    spell_range = f'{self.spell_dict["range"]["distance"]["type"].capitalize()}'
            else:
                spell_range = f'Self ({self.spell_dict["range"]["distance"]["amount"]}-{self.spell_dict["range"]["distance"]["type"].replace("feet","foot").replace("miles","mile")} {self.spell_dict["range"]["type"]})'

        return spell_range

    def _format_spell_components(self) -> str:
        '''
        Function to format the spell components string.

        Returns
        -------
        str
            A friendly string for the spell components.
        '''
        # Format spell components string, accounting for multiple components and possible descriptions.
        spell_components = list()
        for key, value in self.spell_dict['components'].items():
            if value is True:
                spell_components.append(f'{key.capitalize()}')
            else:
                spell_components.append(f'{key.capitalize()} ({value})')
        spell_components = ", ".join(spell_components)

        return spell_components

    def _format_spell_duration(self) -> str:
        '''
        Function to format the spell duration string.

        Returns
        -------
        str
            A friendly string for the spell duration.
        '''
        # Format spell duration string, accounting for types, end conditions, and concentration.
        if self.spell_dict['duration'][0]['type'] == 'timed':
            spell_duration = f'{self.spell_dict["duration"][0]["duration"]["amount"]} {self.spell_dict["duration"][0]["duration"]["type"]}'

            if self.spell_dict["duration"][0]["duration"]["amount"] > 1:
                spell_duration += 's'

            if 'concentration' in self.spell_dict["duration"][0].keys():
                spell_duration += ' (Concentration)'
        elif self.spell_dict['duration'][0]['type'] == 'permanent':
            if 'ends' in self.spell_dict["duration"][0].keys():
                if len(self.spell_dict["duration"][0]["ends"]) == 1:
                    spell_duration = f'Until {self.spell_dict["duration"][0]["ends"][0]}'
                else:
                    spell_duration = f'Until {" or ".join(self.spell_dict["duration"][0]["ends"])}'
            else:
                spell_duration = 'Permanent'
        else:
            spell_duration = self.spell_dict['duration'][0]['type'].capitalize()

        return spell_duration

    def _format_spell_description(self) -> str:
        '''
        Function to format the spell description string.

        Returns
        -------
        str
            A friendly string for the spell description.
        '''
        # Account for nested JSON elements such as lists, tables, and additional "entries".
        spell_description = str()
        spell_entries = self.spell_dict['entries']
        for entry in spell_entries:
            if isinstance(entry, str):
                spell_description += f'{entry}\n'
            elif isinstance(entry, dict):
                if entry['type'] == 'list':
                    for item in entry['items']:
                        spell_description += f'* {item}\n'
                elif entry['type'] == 'table':
                    spell_description += f'**{entry["caption"]}:**\n'
                    # Add table header
                    spell_description += "| " + " | ".join(entry["colLabels"]) + " |\n"
                    # Add table delimiter
                    spell_description += "| " + " --- |" * len(entry["colLabels"]) + "\n"
                    # Add table rows
                    for row in entry["rows"]:
                        spell_description += "| " + " | ".join([str(self._remove_description_decorators(cell)) for cell in row]) + " |\n"
                elif entry['type'] == 'entries':
                    spell_description += f'**{entry["name"]}:** {entry["entries"][0]}\n'
        
        # Account for higher level spell descriptions
        if 'entriesHigherLevel' in self.spell_dict.keys():
            for entry in self.spell_dict['entriesHigherLevel']:
                spell_description += f'**{entry["name"]}:** {entry["entries"][0]}\n'

        return spell_description

    def _remove_description_decorators(self, description: str = None) -> str:
        '''
        Function to remove decorators from spell description.

        Input
        -----
        description : str
            The spell description with any 5e.tools decorators.

        Returns
        -------
        str
            The spell description with 5e.tools decorators removed.
        '''
        # Remove decorators from spell description
        if description is None:
            description = self.spell_description

        # Remove prefix of "{@scaledamage..." decorator and its special text for different scaling that precedes the actual damage dice.
        description = re.sub(r'\{@scaledamage+ [0-9]d[0-9]{1,2}\|[0-9]{1,2}-[0-9]{1,2}\|', '', description)

        # Remove normal prefixes of all other decorators, like "{@damage ", "{@dice ", etc.
        description = re.sub(r'\{@[a-z]+ ', '', description)

        # Remove suffix of "{@chance " decorator and replace with " percent".
        description = description.replace('|||Random reading!|Regular reading}', ' percent')

        # Remove any unique suffixes that contain pipe-separated backend data.
        description = re.sub(r'\|.+}', '', description)

        # Remove closing bracket of separators.
        description = description.replace('}', '')

        return description

    def source_exists(self) -> bool:
        '''
        Function to check if a source exists in the spell index.

        Parameters
        ----------
        source : str
            The name of the source to check.

        Returns
        -------
        bool
            True if the source exists, False otherwise.
        '''
        if self.source_file is not None:
            return True
        else:
            return False

    def spell_exists(self) -> bool:
        '''
        Function to check if a spell exists in the spell index.

        Parameters
        ----------
        name : str
            The name of the spell to check.

        Returns
        -------
        bool
            True if the spell exists, False otherwise.
        '''
        if self.spell_dict is not None:
            return True
        else:
            return False
