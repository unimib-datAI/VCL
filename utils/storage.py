import json
import os
import threading

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from upstash_redis import Redis

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

        self.r = Redis(
            url=read_file(os.path.join(project_root, "settings", "url_redis.txt")),
            token=read_file(os.path.join(project_root, "settings", "token_redis.txt")),
        )

        self._initialized = True

    def _log(self, action: str, key: str, extra: dict = None):
        log_entry = {
            "component": "Storage",
            "action": action,
            "key": key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            log_entry.update(extra)
        print(json.dumps(log_entry))

    def read(self, key: str) -> List[Dict[str, Any]]:
        data = self.r.get(key)
        if data is None:
            self._log("read", key, {"result": "empty"})
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

        self._log("read", key, {"items_returned": len(filtered)})
        return filtered

    def write(self, key: str, element: dict, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)

        data.append(element)
        self.r.set(key, json.dumps(data), ex=1800)

        self._log("write", key, {"new_element": element.get("name", None), "total_items": len(data)})
        return id

    def chat_in_str(self, key: str) -> str:
        data = self.read(key)

        chat_str = ""
        if data:
            for index, doc in enumerate(data):
                chat_str += f"""
                RICHIESTA/DOMANDA {index + 1}:
                - time: {doc["time"]}
                - query: \"{doc.get("query", "")}\"
                - ID doc input: \"{doc.get("docRef", "")}\"
                - ID doc response: \"{doc.get("docOut", "")}\"
                """

        self._log("chat_in_str", key, {"chat_length": len(chat_str)})
        return chat_str

    def get_new_id(self, key: str, data: Optional[List[Dict[str, Any]]] = None):
        if data is None:
            data = self.read(key)

        id_doc = "0"
        if len(data) > 0:
            last_doc_id = data[-1]["name"]
            id_doc = str(int(last_doc_id[last_doc_id.rindex("_") + 1:]) + 1)

        new_id = f"doc_{id_doc}"
        self._log("get_new_id", key, {"new_id": new_id})
        return new_id

    def get_last_element(self, key: str):
        data = self.read(key)
        if not data:
            self._log("get_last_element", key, {"result": "empty"})
            return None

        self._log("get_last_element", key, {"last_element": data[-1].get("name", None)})
        return data[-1]

    def get_element(self, key1: str, key2: str):
        data = self.read(key1)
        if not data:
            self._log("get_element", key1, {"result": "empty"})
            return None

        for d in data:
            if str(d["name"]) == key2:
                self._log("get_element", key1, {"found": key2})
                return d

        self._log("get_element", key1, {"not_found": key2})
        return None

    def clear(self, key: str):
        data = self.read(key)
        new_data = [d for d in data if str(d["name"]).count("_") == 1]
        self.r.set(key, json.dumps(new_data), ex=1800)
        self._log("clear", key, {"remaining_items": len(new_data)})

    def deep_clear(self, key: str):
        self.r.set(key, json.dumps([]), ex=1800)
        self._log("deep_clear", key, {"status": "cleared_all"})
