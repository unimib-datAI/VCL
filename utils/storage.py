import bcrypt
import os
import threading
import pymongo.errors

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Any

from utils.file_manager import FileHandler

class Storage:
    """
    Thread-safe singleton class for managing MongoDB storage.

    Handles:
    - User authentication (registration, login)
    - User-specific data (chat history, documents)
    - User-specific settings (DQL language configuration)
    - In-memory caching for chat and language settings with thread-safe
      access and invalidation.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    # Load env variable from file .env
    load_dotenv()
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, uri_db: str, project_root):
        """
        Initialize the Mongo client and collections.
        (Private constructor, use get_instance())

        Args:
            uri_db (str | None): Mongo URI.
            project_root (Path): Project root directory.

        Raises:
            ValueError: If Mongo credentials cannot be loaded or found.
        """
        # Prevent re-initialization if already done
        if getattr(self, "_initialized", False):
            return

        self._project_root = project_root
        self._file_handler = FileHandler()

        # Load Mongo URI from args, env, or file
        mongo_uri = self._load_data(
            uri_db
        )

        # Initialize MongoDB client and collections
        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        db = client["auth_db"]
        self._users = db["users"]
        
        # Ensure usernames are unique
        self._users.create_index("username", unique=True)
        
        # --- Initialize caches and their locks ---
        self._chat_cache = {}
        self._lang_cache = {}
        self._chat_cache_lock = threading.Lock()
        self._lang_cache_lock = threading.Lock()
        
        self._initialized = True

    @classmethod
    def get_instance(
        cls,
        uri_db=None,
        project_root=None,
    ) -> "Storage":
        """
        Retrieve or create the singleton instance of Storage (thread-safe).

        Args:
            uri_db (str): Mongo URI. (Required on first call)
            project_root (Path): Root project directory. (Required on first call)

        Returns:
            Storage: Singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check lock
                if cls._instance is None:
                    cls._instance = cls(uri_db, project_root)
        return cls._instance

    # ------------------------------
    # --- Initialization Helpers ---
    # ------------------------------

    def _load_data(self, value: Optional[str], env_var: str = "MONGO_URI") -> str:
        """
        Load a credential (e.g., Mongo URI) from argument, environment variable, or fallback file.

        Args:
            value (Optional[str]): The value passed (e.g., from args).
            env_var (str): The name of the environment variable to check.

        Returns:
            str: The loaded credential.

        Raises:
            ValueError: If no value is provided and the file is missing.
        """
        # 1. Check if value is passed directly
        if value:
            return value

        # 2. Check environment variable
        env_value = os.getenv(env_var)
        if env_value:
            return env_value

        # 3. Raise error if nothing found
        raise ValueError(f"Missing or invalid Mongo configuration. Checked arg and env var '{env_var}'")

    # ----------------------
    # --- Authentication ---
    # ----------------------
    
    def register_user(self, username, email, password) -> bool:
        """
        Register a new user with default documents and language settings.

        Args:
            username (str): The desired username.
            email (str): The user's email.
            password (str): The user's plain-text password.

        Returns:
            bool: True if registration was successful, False if user/email exists.
        """
        # Check for existing user or email
        if self._users.find_one({"username": username}) or self._users.find_one({"email": email}):
            return False
        
        # Hash the password
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        
        try:
            # Insert the new user document
            self._users.insert_one({
                "_id": ObjectId(),
                "username": username,
                "email": email,
                "password": hashed_pw,
                "data": {
                    "persisted_docs": self._get_default_docs(),
                    "chat": []
                },
                "settings": {
                    "language": self._get_default_language()
                }
            })
            return True
        except pymongo.errors.DuplicateKeyError:
             # Should be caught by the initial check, but as a safeguard
             return False

    def login_user(self, username, password) -> bool:
        """
        Verify a user's login credentials.

        Args:
            username (str): The username to check.
            password (str): The plain-text password to check.

        Returns:
            bool: True if credentials are valid, False otherwise.
        """
        user = self._users.find_one({"username": username})
        
        if not user:
            return False
        
        # Check the provided password against the stored hash
        if bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            return True
        
        return False

    # ---------------------------
    # --- Document Operations ---
    # ---------------------------
    
    def _get_document(self, user_id, key: tuple, value: str) -> Optional[dict]:
        """
        Private helper to find a specific document in a user's data array.
        Uses MongoDB's $ projection to return only the matched array element.

        Args:
            user_id (str): The user's username.
            key (tuple): A tuple like ("array_name", "field_name_to_match").
                          Example: ("chat", "id")
            value (str): The value to match against.

        Returns:
            Optional[dict]: The found document or None.
        """
        # e.g., "data.chat.id"
        query_key = f"data.{key[0]}.{key[1]}"
        # e.g., {"data.chat.$": 1, "_id": 0}
        projection = {f"data.{key[0]}.$": 1, "_id": 0}
        
        result = self._users.find_one(
            {"username": user_id, query_key: value},
            projection
        )
        
        # Extract the first matched element from the array
        if result and "data" in result and key[0] in result["data"]:
            return result["data"][key[0]][0]
        return None
    
    def get_document_by_id(self, user_id: str, value: str) -> Optional[dict]:
        """Retrieves a single chat document by its 'id'."""
        return self._get_document(user_id, ("chat", "id"), value)
    
    def get_document_by_type(self, user_id: str, value: str) -> Optional[dict]:
        """Retrieves a single persisted document by its 'type_doc'."""
        return self._get_document(user_id, ("persisted_docs", "type_doc"), value)
    
    def get_document_by_name(self, user_id: str, value: str) -> Optional[dict]:
        """Retrieves a single persisted document by its 'name'."""
        return self._get_document(user_id, ("persisted_docs", "name"), value)
    
    def _get_default_docs(self) -> list:
        """
        Load the default documents from the /documents directory.

        Returns:
            list: A list of default document dictionaries.
        """
        doc_names = ["S1 - AN.json", "S2 - AN.json", "M2 - AN.json", "R2 - AN.json"]
        doc_path = os.path.join(self._project_root, "documents")
        
        return [
            self._file_handler.read_file(os.path.join(doc_path, name))
            for name in doc_names
        ]

    def upsert_persisted_doc(self, user_id: str, doc: dict) -> bool:
        """
        Insert or replace (upsert) a document in the 'persisted_docs' array.
        Match is based on the 'type_doc' field.

        Args:
            user_id (str): The user's username.
            doc (dict): The document to upsert. Must contain 'type_doc'.

        Returns:
            bool: True if the database was modified, False otherwise.

        Raises:
            ValueError: If 'type_doc' is missing from the document.
        """
        
        if "type_doc" not in doc:
            raise ValueError("The document must contain a 'type_doc' field.")

        doc.setdefault("updated_at", datetime.utcnow())
        
        doc_type = doc["type_doc"]
        
        # 1. Try to update (replace) an existing doc matching the type
        result = self._users.update_one(
            {"username": user_id, "data.persisted_docs.type_doc": doc_type},
            {"$set": {"data.persisted_docs.$": doc}}
        )

        # 2. If no doc was matched, push it as a new doc
        if result.matched_count == 0:
            result = self._users.update_one(
                {"username": user_id},
                {"$push": {"data.persisted_docs": doc}}
            )

        return result.modified_count > 0

    
    # --------------------------------
    # --- Cache Helper Methods ---
    # --------------------------------
    
    def _invalidate_cache(self, user_id: str, cache: dict, lock: threading.Lock):
        """
        Thread-safely remove a user's data from a specified cache.

        Args:
            user_id (str): The user's username (cache key).
            cache (dict): The cache dictionary (e.g., _chat_cache).
            lock (threading.Lock): The lock for that cache.
        """
        with lock:
            if user_id in cache:
                del cache[user_id]

    def _get_cached_data(self, user_id: str, cache: dict, lock: threading.Lock, projection: dict, data_path: List[str]) -> Optional[Any]:
        """
        Generic helper to retrieve data from cache or database.

        Args:
            user_id (str): The user's username.
            cache (dict): The cache to check.
            lock (threading.Lock): The lock for that cache.
            projection (dict): The MongoDB projection to use.
            data_path (List[str]): The path to the data in the result (e.g., ["data", "chat"]).

        Returns:
            Optional[Any]: The cached or retrieved data, or None.
        """
        # 1. Check cache first (thread-safe)
        with lock:
            if user_id in cache:
                return cache[user_id]
        
        # 2. Not in cache, query DB (outside lock to avoid holding it during I/O)
        result = self._users.find_one(
            {"username": user_id},
            projection
        )
        
        # 3. Extract data by traversing the data_path
        data = None
        if result:
            temp_data = result
            try:
                for key in data_path:
                    temp_data = temp_data[key]
                data = temp_data
            except KeyError:
                data = None # Path not found
        
        # 4. Store in cache (thread-safe)
        with lock:
            cache[user_id] = data
            
        return data

    # -----------------------
    # --- Chat Operations ---
    # -----------------------
    
    def get_chat(self, user_id: str) -> Optional[list]:
        """
        Retrieve the entire chat history for the user, using cache.

        Args:
            user_id (str): The user's username.

        Returns:
            Optional[list]: The user's chat history list, or None.
        """
        return self._get_cached_data(
            user_id,
            self._chat_cache,
            self._chat_cache_lock,
            {"data.chat": 1, "_id": 0},
            ["data", "chat"]
        )
    
    
    def add_chat_message(self, user_id: str, message: dict) -> bool:
        """
        Append a single message to the user's chat array and invalidate cache.

        Args:
            user_id (str): The user's username.
            message (dict): The chat message to add.

        Returns:
            bool: True if the database was modified.
        """
        message.setdefault("timestamp", datetime.utcnow())

        result = self._users.update_one(
            {"username": user_id},
            {"$push": {"data.chat": message}}
        )
        
        # Invalidate cache on successful update
        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)
        
        return result.modified_count > 0
    
    def replace_chat(self, user_id: str, chat: list) -> bool:
        """
        Replace the entire chat history for the user and invalidate cache.

        Args:
            user_id (str): The user's username.
            chat (list): The new chat history list.

        Returns:
            bool: True if the database was modified.
        """
        
        result = self._users.update_one(
            {"username": user_id},
            {"$set": {"data.chat": chat}}
        )
        
        # Invalidate cache on successful update
        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)
        
        return result.modified_count > 0
    
    # ---------------------------
    # --- Language Operations ---
    # ---------------------------
    
    def get_language(self, user_id: str) -> Optional[dict]:
        """
        Retrieve the language configuration for the user, using cache.

        Args:
            user_id (str): The user's username.

        Returns:
            Optional[dict]: The user's language settings dict, or None.
        """
        return self._get_cached_data(
            user_id,
            self._lang_cache,
            self._lang_cache_lock,
            {"settings.language": 1, "_id": 0},
            ["settings", "language"]
        )
    
    
    def _set_element(self, user_id: str, key: Optional[str], value: Any) -> bool:
        """
        Private helper to update a field within 'settings.language'
        and invalidate the language cache.

        Args:
            user_id (str): The user's username.
            key (Optional[str]): The sub-key (e.g., "commands"), or None to
                                 replace the whole 'language' object.
            value (Any): The new value to set.

        Returns:
            bool: True if the database was modified.
        """
        
        # Determine the full update path
        if key:
            update_field = f"settings.language.{key}"
        else:
            update_field = "settings.language"
            
        result = self._users.update_one(
            {"username": user_id},
            {"$set": {update_field: value}}
        )

        # Invalidate cache on successful update
        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._lang_cache, self._lang_cache_lock)

        return result.modified_count > 0
    

    def set_language(self, user_id: str, language: dict) -> bool:
        """Replaces the entire language object for the user."""
        return self._set_element(user_id, None, language)
    
    def set_commands(self, user_id: str, commands: dict) -> bool:
        """Updates the 'commands' sub-field in the user's language settings."""
        return self._set_element(user_id, "commands", commands)
    
    def set_sources(self, user_id: str, sources: dict) -> bool:
        """Updates the 'sources' sub-field in the user's language settings."""
        return self._set_element(user_id, "sources", sources)
    
    def set_what(self, user_id: str, what: dict) -> bool:
        """Updates the 'what' sub-field in the user's language settings."""
        return self._set_element(user_id, "what", what)
    
    def set_default_language(self, user_id: str) -> bool:
        """
        Resets the user's language settings to the default from file.

        Args:
            user_id (str): The user's username.

        Returns:
            bool: True if the database was modified.
        """
        return self.set_language(user_id, self._get_default_language())

    def _get_default_language(self) -> dict:
        """
        Load the default language configuration from file.

        Returns:
            dict: The default language configuration.
        """
        return self._file_handler.read_file(
            os.path.join(
                self._project_root, 
                "documents", 
                "language", 
                "default_language.json"
            )
        )