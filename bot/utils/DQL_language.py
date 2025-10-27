import os

from bot.utils.storage import Storage
from bot.utils.file_manager import read_file

class DQLlanguage():
    full_language = None
    
    def __init__(self, storage: Storage):
        self.storage = storage
        
        self.update_parameters(True)
        
    def get_language(self):
        return self.storage.get_language()
    
    def set_language(self, language: dict):
        self.full_language = self.storage.write(language)
        self.update_parameters()
        
    def set_default_language(self):
        default_language = read_file(os.path.join(
            self.project_root,
            "documents",
            "language",
            "default_language.json"
        ))
        
        self.set_language(default_language)
        
    def update_parameters(self, to_retrieve : bool = False):
        if to_retrieve:
            self.full_language = self.get_language()
            
        self.commands = self.full_language.get("commands", [])
        self.sources = self.full_language.get("sources", [])
        
        self.what_definitions = self.full_language.get("what_definitions", {})
        
        self.set_default_command()
        self.build_command_maps()
        self.build_what_map()
            
    # --- COMMANDS FUNCTIONS --- #
            
    def build_command_maps(self):
        """
        Build mapping dictionaries for command keys to commands and descriptions.
        """
        self.key_command_map = {}
        self.command_description_map = {}
        
        for cmd in self.full_language.get("commands", []):
            self.key_command_map.update({cmd['key']: cmd['command']})
            self.command_description_map.update({cmd['command']: cmd['description']})
            
    def get_command_from_key(self, key: str) -> str:
        """
        Get the command string associated with a single-letter shortcut key.

        Args:
            key (str): A single-letter command key.

        Returns:
            str: The corresponding command, or "altro" if not found.
        """
        return self.key_command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        """
        Get the description of a command.

        Args:
            key (str): Either a command name or a single-letter shortcut key.

        Returns:
            str: The description of the command, or an empty string if not found.
        """
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self.command_description_map.get(key, "")
    
    
    def set_default_command(self):
        default = [cmd for cmd in self.commands if cmd.get('default', False)]
        
        if not default:
            default = [self.commands[-1]]
        
        self.default_command = default[0]
        
        
    # --- WHAT FUNCTIONS --- #
    def build_what_map(self):
        what_map = {}
        
        for src in self.sources:
            what_map.update({src.get("name", ""): src.get("available_what", [])})
            
        self.what_map = what_map
        
        
    def get_available_what(self, sources: list) -> dict:
        what_elements = []
        
        if sources:
            # This block now only runs if 'sources' contains at least one item.
            what_elements = list(
                set.intersection(
                    *[set(self.what_map.get(source, [])) for source in sources]
                )
            )
        
        available_what = []
        for what in what_elements:
            available_what.append((what,
                                   self.get_what_definition(what)))
        
        return available_what
    
    def get_what_definition(self, element):
        return self.what_definitions.get(element, "")
    