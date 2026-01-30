from copy import deepcopy

from logic.orchestrator import Orchestrator
from utils.config import Config

class DQLModel():
    def __init__(self, username):
        self.username = username
        self.config = deepcopy(Config.get_instance())

    @property
    def name(self):
        return self.username

    def initialize(self, _):
        user = "LDQL-U" if "LDQL-U" in self.username else self.username
        self.config.get_storage().register_user(user, f"{user}@gmail.com", f"Admin123!")
        
        self.config.handle_login(user.lower(), "Altro")
        self.config.set_sources_id("vitali")

    def query(self, question: str) -> str:
        self.config.set_chat_id()
        self.config.set_request_id()
        
        orchestrator = Orchestrator(self.config)
        
        return orchestrator.chat(question)
