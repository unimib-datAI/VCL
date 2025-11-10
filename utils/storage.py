import bcrypt
import os
import threading
import pymongo

from bson import ObjectId
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from typing import Optional

from utils.file_manager import FileHandler

class Storage:
    
    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, uri_db: str, project_root):
        """
        Initialize the Mongo client with credentials and user context.

        Args:
            uri_db (str | None): Mongo URI.
            project_root (Path): Project root directory.

        Raises:
            ValueError: If Mongo credentials cannot be loaded or found.
        """
        if getattr(self, "_initialized", False):
            return

        self.project_root = project_root
        self.file_handler = FileHandler()

        mongo_uri = self._load_data(
            uri_db, os.path.join(self.project_root, "settings", "mongo_uri.txt")
        )

        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        db = client["auth_db"]
        self.users = db["users"]
        
        self.users.create_index("username", unique=True)
        
        self._initialized = True

    @classmethod
    def get_instance(
        cls,
        uri_db=None,
        project_root=None,
    ) -> "Storage":
        """
        Retrieve or create the singleton instance of Storage.

        Args:
            uri_db (str): Mongo URI. (Required on first call)
            project_root (Path): Root project directory. (Required on first call)

        Returns:
            Storage: Singleton instance.
            
        Raises:
            ValueError: If called for the first time without required arguments.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(uri_db, project_root)
        return cls._instance

    # ------------------------------
    # --- Initialization Helpers ---
    # ------------------------------

    def _load_data(self, value: Optional[str], path: str) -> str:
        """
        Load a credential (e.g., Mongo URI or token) from argument or fallback file.
        """
        if not value and os.path.exists(path) and os.path.isfile(path):
            value = self.file_handler.read_file(path)

        if not value:
            raise ValueError(f"Missing or invalid Mongo configuration at: {path}")

        self.file_handler.write_file(path, value)
        return value

    # ----------------------
    # --- Authentication ---
    # ----------------------
    
    def register_user(self, username, email, password):
        if self.users.find_one({"username": username}) or self.users.find_one({"email": email}):
            return False
        
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        
        try:
            self.users.insert_one({
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
             return False

    def login_user(self, username, password):
        user = self.users.find_one({"username": username})
        
        if not user:
            return False
        
        if bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            return True
        
        return False

    # ---------------------------
    # --- Document Operations ---
    # ---------------------------
    
    def _get_document(self, user_id, key, value):
        """Helper to find a specific document in the current user's array."""
        query_key = f"data.{key[0]}.{key[1]}"
        projection = {f"data.{key[0]}.$": 1, "_id": 0}
        
        result = self.users.find_one(
            {"username": user_id, query_key: value},
            projection
        )
        
        if result and "data" in result and key[0] in result["data"]:
            return result["data"][key[0]][0]
        return None
    
    def get_document_by_id(self, user_id, value):
        return self._get_document(user_id, ("chat", "id"), value)
    
    def get_document_by_type(self, user_id, value):
        return self._get_document(user_id, ("persisted_docs", "type_doc"), value)
    
    def get_document_by_name(self, user_id, value):
        return self._get_document(user_id, ("persisted_docs", "name"), value)
    
    def _get_default_docs(self) -> list:
        """
        Load and the default documents from file.
        """
        doc_names = ["S1 - AN.json", "S2 - AN.json", "M2 - AN.json", "R2 - AN.json"]
        doc_path = os.path.join(self.project_root, "documents")
        
        return [
            self.file_handler.read_file(os.path.join(doc_path, name))
            for name in doc_names
        ]

    def upsert_persisted_doc(self, user_id,  doc: dict) -> bool:
        """
        Insert or replace a persisted_doc for the current user.
        """
        
        if "type_doc" not in doc:
            raise ValueError("The document must contain a 'type_doc' field.")

        doc.setdefault("updated_at", datetime.utcnow())
        
        doc_type = doc["type_doc"]
        
        result = self.users.update_one(
            {"username": user_id, "data.persisted_docs.type_doc": doc_type},
            {"$set": {"data.persisted_docs.$": doc}}
        )

        if result.matched_count == 0:
            result = self.users.update_one(
                {"username": user_id},
                {"$push": {"data.persisted_docs": doc}}
            )

        return result.modified_count > 0

    
    # -----------------------
    # --- Chat Operations ---
    # -----------------------
    
    def get_chat(self, user_id):
        """Retrieve the entire chat history for the current user."""
        result = self.users.find_one(
            {"username": user_id},
            {"data.chat": 1, "_id": 0}
        )
        if result and "data" in result:
            return result["data"].get("chat")
        return None
    
    def add_chat_message(self, user_id, message: dict) -> bool:
        """
        Append a single message to the current user's chat array.
        """
        message.setdefault("timestamp", datetime.utcnow())

        result = self.users.update_one(
            {"username": user_id},
            {"$push": {"data.chat": message}}
        )
        return result.modified_count > 0
    
    # ---------------------------
    # --- Language Operations ---
    # ---------------------------
    
    def get_language(self, user_id):
        """
        Retrieve the stored language configuration for the current user.
        """
        result = self.users.find_one(
            {"username": user_id},
            {"settings.language": 1, "_id": 0}
        )
        
        if result and "settings" in result:
            return result["settings"]["language"]
            
        return None
    
    def _set_element(self, user_id, key: Optional[str], value) -> bool:
        """
        Update or set a specific language setting for the current user.
        """
        
        if key:
            update_field = f"settings.language.{key}"
        else:
            update_field = "settings.language"
            
        result = self.users.update_one(
            {"username": user_id},
            {"$set": {update_field: value}}
        )

        return result.modified_count > 0

    def set_language(self, user_id, language: dict):
        return self._set_element(user_id, None, language)
    
    def set_commands(self, user_id, commands: dict):
        return self._set_element(user_id, "commands", commands)
    
    def set_sources(self, user_id, sources: dict):
        return self._set_element(user_id, "sources", sources)
    
    def set_what(self, user_id, what: dict):
        return self._set_element(user_id, "what", what)
    
    def set_default_language(self, user_id):
        """
        Load and store the default language configuration for the current user.
        """
        return self.set_language(user_id, self._get_default_language())

    def _get_default_language(self) -> dict:
        """
        Load and the default language configuration from file.
        """
        return self.file_handler.read_file(
            os.path.join(
                self.project_root, 
                "documents", 
                "language", 
                "default_language.json"
            )
        )