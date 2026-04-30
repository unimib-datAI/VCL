"""Evaluation adapter for the local DQL pipeline."""
import requests
import time

from copy import deepcopy
from utils.config import Config

class DQLModel():
    """Wrap DQL so it can be called through the evaluation registry."""

    def __init__(self, llm, username, same_chat = False):
        """Store model configuration and chat reuse settings."""
        self.llm = llm
        self.username = username
        self.register = deepcopy(Config.get_instance()).register_user
        
        self.same_chat = same_chat
        self.id_chat = 0

    @property
    def name(self):
        """Return the display name used in evaluation outputs."""
        return f"DQL ({self.llm})"

    def initialize(self, _):
        """Prepare a test user and default source context."""
        self.register(self.username, f"{self.username}@gmail.com", f"Admin123!")
        self.id_chat = 0

    def query(self, question: str) -> str:
        """Send one question to the DQL orchestrator."""
        if not self.same_chat:
            self.id_chat += 1
        
        payload = {
            "prompt": question,
            "user_id": self.username,
            "chat_id": str(self.id_chat),
            "request_id": f"{str(self.id_chat)}{str(int(time.time))}",
            "source_id": self.username
        }
        
        try:
            response = requests.post("http://localhost:9000/api/answer", json=payload)
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "role": "assistant",
                "time": str(int(time.time)),
                "model": "DQL",
                
                "id": payload["request_id"],
                
                "ids": {
                    "user": payload["user_id"],
                    "session": payload["chat_id"],
                    "request": payload["request_id"],
                },
                
                "content": "Errore durante la chiamata al modello DQL. Per favore riprova più tardi.",
                "result": "Errore durante la chiamata al modello DQL. Per favore riprova più tardi.",
                
                "details": {
                    "prompt": "", 
                    "prompt_process": "Errore durante la chiamata al modello DQL.",
                    "tasks": []
                }
            }
