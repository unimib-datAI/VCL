from upstash_redis import Redis
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from utils.file_manager import read_file

class Storage:
    def __init__(self):
        self.r = Redis(url=read_file(os.path.join(project_root, "settings", "url_redis.txt")), 
                       token=read_file(os.path.join(project_root, "settings", "token_redis.txt")))

    def read(self, key: str) -> List[Dict[str, Any]]:
        data = self.r.get(key)
        
        if data is None:
            return []
        
        return json.loads(data)
    
    def write(self, key: str, query: str, docRef: str, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)

        now = datetime.now(timezone.utc)

        filtered = []
        for d in data:
            t = datetime.fromisoformat(d["time"])
            
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            
            if int(abs((now - t).total_seconds() / 60)) < 60:
                filtered.append(d)
        
        id_doc = "0"
        if len(filtered) > 0:
            last_doc_id = filtered[-1]["docOut"]
            id_doc = str(int(last_doc_id[last_doc_id.index("_") + 1:]) + 1)
            
        filtered.append({
            "time": now.isoformat(),
            "query": query,
            "docRef": docRef,
            "docOut": f"doc_{id_doc}"
        })

        self.r.set(key, json.dumps(filtered), ex=1800)

    def clear(self, key: str):
        self.r.set(key, json.dumps([]))
