import json
import os
import threading
from typing import List, Dict, Any, Optional
from upstash_redis import Redis

from utils.file_manager import FileHandler


class Storage:
    """
    Singleton class responsible for managing persistent storage using Upstash Redis.

    Handles:
    - Initialization of Redis client with credentials from local files or parameters.
    - Reading and writing structured data (documents, chat history, languages, etc.).
    - Utility methods for retrieving and filtering data from Redis.

    Attributes:
        project_root (Path): Root directory of the project.
        user_id (str): Unique identifier of the user.
        r (Redis): Redis client instance.
    """
    
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, user_id, url_db, token_db, project_root):
        """
        Initialize the Redis client with credentials and user context.

        Args:
            user_id (str): Identifier for the current user.
            url_db (str | None): Redis URL.
            token_db (str | None): Redis token.
            project_root (Path): Project root directory.

        Raises:
            ValueError: If Redis credentials cannot be loaded or found.
        """
        if getattr(self, "_initialized", False):
            return  # Prevent re-initialization in singleton context

        self.project_root = project_root
        self.user_id = user_id

        # Load Redis credentials
        redis_url = self._load_data(
            url_db, os.path.join(self.project_root, "settings", "url_db.txt")
        )
        redis_token = self._load_data(
            token_db, os.path.join(self.project_root, "settings", "token_db.txt")
        )

        # Initialize Redis client
        self.r = Redis(url=redis_url, token=redis_token)
        self._initialized = True

    @classmethod
    def get_instance(
        cls,
        user_id=None,
        url_db=None,
        token_db=None,
        project_root=None,
    ) -> "Storage":
        """
        Retrieve or create the singleton instance of Storage.

        Args:
            project_root (Path): Root project directory.
            user_id (str): Unique user ID.
            url_db (str): Redis URL.
            token_db (str): Redis token.

        Returns:
            Storage: Singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(user_id, url_db, token_db, project_root)
        return cls._instance

    # -----------------------
    # --- Private Helpers ---
    # -----------------------

    def _load_data(self, value: Optional[str], path: str) -> str:
        """
        Load a credential (e.g., Redis URL or token) from argument or fallback file.

        Args:
            value (str | None): Provided value, if available.
            path (str): File path for fallback.

        Returns:
            str: Loaded and validated credential value.

        Raises:
            ValueError: If no valid value can be found.
        """
        if not value and os.path.exists(path) and os.path.isfile(path):
            value = FileHandler().read_file(path)

        if not value:
            raise ValueError(f"Missing or invalid Redis configuration at: {path}")

        # Persist value to ensure it's saved
        FileHandler().write_file(path, value)
        return value

    # ---------------------------
    # --- Document Operations ---
    # ---------------------------

    def get_documents(self, key: str) -> List[Dict[str, Any]]:
        """
        Retrieve all documents stored under a given Redis key.

        Args:
            key (str): Redis key.

        Returns:
            list[dict]: List of stored documents, or empty list if none found.
        """
        data = self.r.get(key)
        if not data:
            return []
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return []

    def set_documents(
        self,
        key: str,
        element: dict,
        ttl: Optional[int] = 0,
        data: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Append a new element to an existing Redis document list and save it.

        Args:
            key (str): Redis key.
            element (dict): Element to append.
            ttl (int, optional): Expiration time (seconds). Defaults to 0 (no expiry).
            data (list[dict], optional): Pre-loaded document list. If None, fetched from Redis.
        """
        if data is None:
            data = self.get_documents(key)

        data.append(element)

        if ttl and ttl > 0:
            self.r.set(key, json.dumps(data), ex=ttl)
        else:
            self.r.set(key, json.dumps(data))

    def chat_in_str(self, key: str) -> str:
        """
        Return a string representation of stored chat sessions.

        Args:
            key (str): Redis key for chat history.

        Returns:
            str: Stringified representation of chat history.
        """
        data = self.get_documents(key)
        if not data:
            return ""

        chat_entries = [
            {
                "index": index + 1,
                "query": doc.get("query", ""),
                "used_documents": doc.get("used_documents", ""),
                "id": doc.get("id", ""),
            }
            for index, doc in enumerate(data)
        ]
        return str(chat_entries)

    # --------------------------
    # --- Document Retrieval ---
    # --------------------------

    def get_documents_by_id(self, key: str, element_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its 'id' field."""
        return self._get_document(key, "id", element_id)

    def get_documents_by_type(
        self, key: str, element_type: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its 'type_doc' field."""
        return self._get_document(key, "type_doc", element_type)

    def get_documents_by_name(
        self, key: str, element_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its 'name' field."""
        return self._get_document(key, "name", element_name)

    def _get_document(self, key: str, field: str, value: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the first document where a given field matches the provided value.

        Args:
            key (str): Redis key.
            field (str): Field name to match.
            value (str): Expected value.

        Returns:
            dict | None: Matching document or None if not found.
        """
        data = self.get_documents(key)
        if not isinstance(data, list):
            return None

        for item in data:
            if item.get(field) == value:
                return item
        return None

    # ---------------------------
    # --- Language Management ---
    # ---------------------------

    def get_language(self) -> Dict[str, Any]:
        """
        Retrieve the stored language configuration for the user.

        Returns:
            dict: Language definition, or empty dict if not found.
        """
        key = f"{self.user_id}_language"
        language = self.r.get(key)
        return json.loads(language) if language else {}

    def set_language(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a new language configuration for the user.

        Args:
            element (dict): Language definition.

        Returns:
            dict: The stored language.
        """
        key = f"{self.user_id}_language"
        self.r.set(key, json.dumps(element))
        return element

    def set_default_language(self) -> Dict[str, Any]:
        """
        Load and store the default language configuration from file.

        Returns:
            dict: The default language definition.
        """
        path = os.path.join(
            self.project_root, "documents", "language", "default_language.json"
        )
        default_language = FileHandler().read_file(path)
        return self.set_language(default_language)
