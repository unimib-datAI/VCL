import requests

from config import Config

class Rewriting:
    command = None
    
    def __init__(self, query: str, cfg: Config):
        self.original_query = query
        
        data = {
            "message": query,
            "thread_id": "1"
        }

        response = requests.post(cfg.url, json=data, headers=cfg.headers)

        if response.status_code == 200:
            self.command = response.text
