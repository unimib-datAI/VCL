import requests
import socket
import json

from utils.config import Config

class Rewriting:
    def __init__(self, cfg: Config):
        self.url = cfg.url
        self.headers = cfg.headers
        
        hostname = socket.gethostname()
        self.ip = socket.gethostbyname(hostname)
        
    def rewrite(self, query):
        data = {
            "message": query,
            "thread_id": str(self.ip)
        }

        response = requests.post(self.url, json=data, headers=self.headers)

        if response.ok:
            return response.json()
        else:
            return {}
