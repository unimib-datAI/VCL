import os

from bot.utils.config import Config
from bot.utils.DQL_language import DQLlanguage

class CommandClassifier:
    
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Translator")
        self.project_root = cfg.project_root
        
        self.dqlLanguage = DQLlanguage(cfg.storage)
    
    def classify(self, query: str) -> dict:
        language_commands = self.commands_string(self.dqlLanguage.commands)
        
        query_dict = {
            "query": query,
            "language_commands": language_commands,
            "default_key": self.dqlLanguage.default_command.get("key", ""),
            "feedback": ""
        }
        
        command_info = {}
        
        try:
            if query_dict.get("query", "").strip():
                result = self.llm.invoke_from_file(
                    os.path.join(self.project_root,
                                 "documents",
                                 "prompts", 
                                 "rewriting", 
                                 "3 - IntentClassification.json"),
                    query_dict,
                    True
                )
                
                result = self.dqlLanguage.get_command_from_key(result)

                command_info = {
                    "name": result,
                    "description": self.dqlLanguage.get_description_from_command(result),
                }
                
                status = "Done"
            else:
                raise Exception()
        except Exception:
            command_info = {
                "name": "altro",
                "description": self.dqlLanguage.get_description_from_command("altro"),
            }
            status = "Error"
        
        self.logger.info(f"Intent Classification: {command_info.get("name", "altro")} - {status}")
        
        return command_info
    
    @staticmethod
    def commands_string(commands) -> str:
        """
        Generate a formatted string of available commands for logging or display.

        Returns:
            str: A formatted string listing all available commands.
        """
        commands_list = [
            f"- \"{cmd['key']}\": {cmd['description']}"
            for cmd in commands
        ]
            
        return "\n".join(commands_list)