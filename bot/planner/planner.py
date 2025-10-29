import os

from bot.utils.config import Config
from bot.utils.DQL_language import DQLlanguage
from bot.utils.file_manager import read_file

class Planner:
    def __init__(self, cfg: Config):
        self.logger = cfg.get_logger("Planner")
        self.project_root = cfg.project_root
        self.dql = DQLlanguage(cfg)
        self.commands = self.retrieve_commands()

    def decompose(self, query: dict) -> list[dict]:
        ops = []
        
        if self.commands.get(query.get("command", ""), ["*"]):
            if len(query.get("from", [])) > 1:
                ops = self.get_operation_list(query, query.get("command", ""), "integra")
            else:
                ops = [query]
        else:
            middle_command = self.find_middle_command(query.get("what", ""))
            ops = self.get_operation_list(query, middle_command, query.get("command", ""))
            
        return ops
    
    def get_operation_list(self, query, middle_command, final_command):
        ops = [
            {
                "id": f"{query.get("id", "")}_{str(i)}", 
                "command": middle_command,
                "from": [document],
                "what": query.get("what", "")
            }
            for i, document in enumerate(query.get("from", []))
        ]
        
        final_op = {
            "id": query.get("id", ""), 
            "command": final_command,
            "from": [o["id"] for o in ops],
            "how": query.get("how", {})
        }
        
        ops.append(final_op)
        
        return ops
    
    def find_middle_command(self, what: str) -> str:
        middle_command = ""
        
        for key in self.commands.keys():
            if what in self.commands.get(key, []):
                middle_command = key
                break
        
        self.logger.info(f"Middle Command: {middle_command}")
        return middle_command

    def retrieve_commands(self) -> dict:
        commands = {}
        
        commands_data = self.dql.commands
        
        for command in commands_data:
            if command.get("command", ""):
                commands[command.get("command")] = command.get("atomic", [])
        
        return commands
