import requests
import socket

from utils.config import Config

class DQL:
    def __init__(self, nl_query, structured_query):
        self.nl_query = nl_query
        self.dql_query = structured_query
    

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

        if response.status_code == 200:
            return DQL(query, response.text)
        else:
            return DQL(query, None)
