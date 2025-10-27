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

from bot.utils.file_manager import read_file

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
    def get_instance(cls, logger = None, project_root = None, user_id = None):
        """
        Retrieve the singleton instance of Storage.

        Returns:
            Storage: The singleton Storage instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(logger, project_root, user_id)
        return cls._instance

    def __init__(self, logger, project_root, user_id):
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
        
        self.user_id = user_id

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

        return json.loads(data)

    def write(
        self, 
        key: str, 
        element: dict,
        ttl: Optional[int] = 0,
        data: Optional[List[Dict[str, Any]]] = None
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
        if ttl > 0:
            # Save data with TTL of 60 minutes
            self.r.set(key, json.dumps(data), ex=ttl)
        else:
            self.r.set(key, json.dumps(data))

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
            chat_str = str([{
                "index": index + 1,
                "query": {doc.get("query", "")},
                "used_documents": doc.get("used_documents", ""),
                "id": doc.get("id", "")
                } for index, doc in enumerate(data)])

        return chat_str
    
    def get_element_by_id(self, key: str, element_id: str) -> Optional[Dict[str, Any]]:
        return self.get_element(key, "id", element_id)
    
    def get_element_by_type(self, key: str, element_type: str) -> Optional[Dict[str, Any]]:
        return self.get_element(key, "type_doc", element_type)
    
    def get_element_by_name(self, key: str, element_name: str) -> Optional[Dict[str, Any]]:
        return self.get_element(key, "name", element_name)
    
    def get_element(self, key: str, field: str, element: str) -> Optional[Dict[str, Any]]:
        data = self.read(key)
        for element in data:
            if element.get(field, "") == element:
                return element
        return None


    def deep_clear(self, key: str):
        """
        Completely clear all elements from Redis for a given key.

        Args:
            key (str): Redis key to clear.
        """
        self.r.set(key, json.dumps([]), ex=1800)
            
    # --- Language Functions --- #
    
    def get_language(self):
        language = self.read(f"{self.user_id}_language")
        
        if not language:
            return self.set_default_language()
        
        return language[0]
    
    def write_language(self, element):
        self.write(f"{self.user_id}_language", element)
        return element
