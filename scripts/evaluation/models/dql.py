from copy import deepcopy

from logic.orchestrator import Orchestrator
from utils.config import Config

class DQLModel():
    def __init__(self, username, same_chat = False):
        self.username = username
        self.config = deepcopy(Config.get_instance())
        
        self.same_chat = same_chat
        self.id_chat = 0

    @property
    def name(self):
        return self.username

    def initialize(self, _):
        user = "LDQL-U" if "LDQL-U" in self.username else self.username
        self.config.get_storage().register_user(user, f"{user}@gmail.com", f"Admin123!")
        
        self.config.handle_login(user.lower(), "Altro")
        self.config.set_sources_id("vitali")

    def query(self, question: str) -> str:
        orchestrator = Orchestrator(self.config, self.username, str(self.id_chat))
        
        if not self.same_chat:
            self.id_chat += 1
        
        return orchestrator.chat(question)
