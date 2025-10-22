import os

from bot.utils.config import Config
from bot.utils.file_manager import read_file

class CommandClassifier:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.commands = self.retrieve_commands()
        self.build_command_maps()
    
    def classify(self, query: str) -> dict:
        language_commands, default_key = self.commands_string()
        
        query_dict = {
            "query": query,
            "language_commands": language_commands,
            "default_key": default_key,
            "feedback": ""
        }
        
        command_info = {}
        
        try:
            if query_dict.get("query", "").strip():
                result = self.llm.invoke_from_file(
                    os.path.join(self.project_root, "prompts", "rewriting", "3 - IntentClassification.json"),
                    query_dict,
                    True
                )
                
                result = self.get_command_from_key(result)

                command_info = {
                    "name": result,
                    "description": self.get_description_from_command(result),
                }
                
                status = "Done"
            else:
                raise Exception()
        except Exception:
            command_info = {
                "name": "altro",
                "description": self.get_description_from_command("altro"),
            }
            status = "Error"
        
        self.logger.info(f"Intent Classification: {command_info.get("name", "altro")} - {status}")
        
        return command_info
        
    def retrieve_commands(self) -> list:
        """
        Retrieve the list of available commands from the commands.json file.

        Returns:
            list: A list of command dictionaries.
        """
        commands_path = os.path.join(
            self.project_root,
            "documents",
            "language",
            "commands.json"
        )
        commands_data = read_file(commands_path)
        
        return commands_data.get("commands", [])
    
    def commands_string(self) -> str:
        """
        Generate a formatted string of available commands for logging or display.

        Returns:
            str: A formatted string listing all available commands.
        """
        commands_list = [
            f"- \"{cmd['key']}\": {cmd['description']}"
            for cmd in self.commands
        ]
        
        default_key = [cmd['key'] for cmd in self.commands if cmd.get('default', False)]
        if not default_key:
            default_key = [self.commands[-1].get('key')]
            
        return "\n".join(commands_list), default_key[0]
    
    def build_command_maps(self):
        """
        Build mapping dictionaries for command keys to commands and descriptions.
        """
        self.key_command_map = {
            cmd['key']: cmd['command']
            for cmd in self.commands
        }
        
        self.command_description_map = {
            cmd['command']: cmd['description']
            for cmd in self.commands
        }
    
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