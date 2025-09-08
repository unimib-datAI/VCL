from upstash_redis import Redis
import json
import os
import threading
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from utils.file_manager import read_file

project_root = Path(__file__).resolve().parent.parent

class Storage:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        
        self.r = Redis(url=read_file(os.path.join(project_root, "settings", "url_redis.txt")), 
                       token=read_file(os.path.join(project_root, "settings", "token_redis.txt")))
        
        self._initialized = True

    def read(self, key: str) -> List[Dict[str, Any]]:
        data = self.r.get(key)
        
        if data is None:
            return []
        
        data = json.loads(data)
        
        now = datetime.now(timezone.utc)

        filtered = []
        for d in data:
            t = datetime.fromisoformat(d["time"])
            
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            
            if int(abs((now - t).total_seconds() / 60)) < 60:
                filtered.append(d)
                
        return filtered
    
    def write(self, key: str, element: dict, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)
            
        data.append(element)
        self.r.set(key, json.dumps(data), ex=1800)
        
        return id
    
    def chat_in_str(self, key):
        data = self.read(key)
    
        chat_str = ""
        if not (data == []):
            
            for i in range(len(data)):
                chat_str += f"""
                RICHIESTA/DOMANDA {i}
                - time: {data[i]["time"]}
                - query: \"{data[i]["query"]}\""
                - ID doc input: \"{data[i]["docRef"]}\"
                - ID doc response: \"{data[i]["docOut"]}\""
                
                """
        
        return chat_str
        
    def get_new_id(self, key: str, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)
        
        id_doc = "0"
        if len(data) > 0:
            last_doc_id = data[-1]["name"]
            id_doc = str(int(last_doc_id[last_doc_id.rindex("_") + 1:]) + 1)
        
        return f"doc_{id_doc}"
    
    def get_last_element(self, key: str):
        data = self.read(key)
        
        if data == []:
            return None

        return data[-1]
    
    def get_element(self, key1, key2):
        data = self.read(key1)
        
        if data == []:
            return None

        for d in data:
            if str(d["name"]) == key2:
                return d
        
        return None
    
    def clear(self, key: str):
        data = self.read(key)
        new_data = []
        
        for d in data:
            if str(d["name"]).count("_") == 1:
                new_data.append(d)
            
        self.r.set(key, json.dumps(new_data))
        
    def deep_clear(self, key: str):
        self.r.set(key, json.dumps([]))
