"""
Storage module for managing persistent conversation and document data
using Upstash Redis.

Responsibilities:
- Provide a thread-safe singleton interface for accessing Redis.
- Read, write, and manage chat session data with time-based filtering.
- Generate unique document IDs for stored items.
- Support cleanup operations for stored chat histories.

Dependencies:
- upstash_redis.Redis: Redis client for cloud storage.
- utils.file_manager.read_file: Reads Redis credentials from settings files.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from upstash_redis import Redis

from utils.file_manager import read_file

# Root path of the project (two levels up from this file)
project_root = Path(__file__).resolve().parent.parent

class Storage:
    """
    Singleton class for managing Redis-based storage.

    This class is responsible for persisting and retrieving conversation history
    and related data. It ensures only one Redis connection exists throughout
    the application.

    Attributes:
        r (Redis): Redis client instance connected to Upstash.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, logger = None, project_root = None):
        """
        Retrieve the singleton instance of Storage.

        Returns:
            Storage: The singleton Storage instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(logger, project_root)
        return cls._instance

    def __init__(self, logger, project_root):
        """
        Initialize the Redis client with credentials from settings files.

        Raises:
            FileNotFoundError: If Redis URL or token files are missing.
        """
        if getattr(self, "_initialized", False):
            return

        self.project_root = project_root
        self.logger = logger
        
        # Initialize Redis client with credentials from settings
        self.r = Redis(
            url=read_file(os.path.join(self.project_root, "settings", "url_redis.txt")),
            token=read_file(os.path.join(self.project_root, "settings", "token_redis.txt")),
        )

        self._initialized = True

    def read(self, key: str) -> List[Dict[str, Any]]:
        """
        Read data from Redis and filter out old entries.

        Args:
            key (str): Redis key to read from.

        Returns:
            List[Dict[str, Any]]: List of documents from the last 60 minutes.
        """
        data = self.r.get(key)
        if data is None:
            return []

        data = json.loads(data)
        now = datetime.now(timezone.utc)

        # Filter out documents older than 60 minutes
        filtered = []
        for d in data:
            t = datetime.fromisoformat(d["time"])
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if int(abs((now - t).total_seconds() / 60)) < 60:
                filtered.append(d)

        return filtered

    def write(
        self, key: str, element: dict, data: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Write a new element to Redis.

        Args:
            key (str): Redis key to write to.
            element (dict): Document or chat entry to store.
            data (list, optional): Existing data to append to. If None, it is read from Redis.

        """
        if data is None:
            data = self.read(key)

        data.append(element)
        # Save data with TTL of 30 minutes
        self.r.set(key, json.dumps(data), ex=1800)

    def chat_in_str(self, key: str) -> str:
        """
        Retrieve chat history as a formatted string.

        Args:
            key (str): Redis key representing the chat session.

        Returns:
            str: Formatted chat history string.
        """
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

        return chat_str

    def get_new_id(self, key: str, data: Optional[List[Dict[str, Any]]] = None):
        """
        Generate a new unique document ID for a chat session.

        Args:
            key (str): Redis key representing the chat session.
            data (list, optional): Existing data to base ID generation on.

        Returns:
            str: Newly generated document ID.
        """
        if data is None:
            data = self.read(key)

        id_doc = "0"
        if len(data) > 0:
            last_doc_id = data[-1]["name"]
            id_doc = str(int(last_doc_id[last_doc_id.rindex("_") + 1 :]) + 1)

        new_id = f"doc_{id_doc}"
        return new_id

    def get_last_element(self, key: str):
        """
        Get the most recent element from Redis.

        Args:
            key (str): Redis key to read from.

        Returns:
            dict | None: Last element if exists, otherwise None.
        """
        data = self.read(key)
        if not data:
            return None

        return data[-1]

    def get_element(self, key1: str, key2: str):
        """
        Retrieve a specific element by its name field.

        Args:
            key1 (str): Redis key to read from.
            key2 (str): Document ID to search for.

        Returns:
            dict | None: Found element or None if not found.
        """
        data = self.read(key1)
        if not data:
            return None

        for d in data:
            if str(d["name"]) == key2:
                return d
            
        return None

    def clear(self, key: str):
        """
        Clear intermediate elements but keep base-level entries.

        Args:
            key (str): Redis key to clear.
        """
        data = self.read(key)
        # Keep only elements with names containing a single underscore
        new_data = [d for d in data if str(d["name"]).count("_") == 1]
        self.r.set(key, json.dumps(new_data), ex=1800)

    def deep_clear(self, key: str):
        """
        Completely clear all elements from Redis for a given key.

        Args:
            key (str): Redis key to clear.
        """
        self.r.set(key, json.dumps([]), ex=1800)
