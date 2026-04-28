from copy import deepcopy

from api.dqlEngine.orchestrator.orchestrator import Orchestrator
from utils.config import Config

class DQLModel():
    def __init__(self, llm, username, same_chat = False):
        self.llm = llm
        self.username = username
        self.config = deepcopy(Config.get_instance())
        
        self.same_chat = same_chat
        self.id_chat = 0

    @property
    def name(self):
        return f"DQL ({self.llm})"

    def initialize(self, _):
        self.config.get_storage().register_user(self.username, f"{self.username}@gmail.com", f"Admin123!")
        
        self.config.handle_login(self.username.lower(), "Altro")
        self.config.set_sources_id("vitali")

    def query(self, question: str) -> str:
        orchestrator = Orchestrator(self.config, self.username, str(self.id_chat))
        
        if not self.same_chat:
            self.id_chat += 1
        
        return orchestrator.chat(question)
