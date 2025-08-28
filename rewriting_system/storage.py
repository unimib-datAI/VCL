import redis
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class Storage:
    def __init__(self):
        self.r = {}

    def read(self, key: str) -> List[Dict[str, Any]]:
        if not (key in self.r.keys()):
            return []
        
        return self.r.get(key)

    def write(self, key: str, query: str, docRef: str, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)

        data.append({
            "time": datetime.now().isoformat(),
            "query": query,
            "docRef": docRef,
            "docOut": f"doc_{len(data)}"
        })

        self.r.update({key: data})

    def clear(self, key: str):
        self.r.update({key: []})
