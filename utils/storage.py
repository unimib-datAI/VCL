"""MongoDB persistence layer for users, documents, chats, and battle votes."""

import bcrypt
import os
import re
import threading

from pathlib import Path
from copy import deepcopy
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Any, Dict, Tuple

from utils.file_manager import FileHandler


class Storage:
    """
    Thread-safe Singleton class for managing MongoDB interactions and in-memory caching.

    This class serves as the persistence layer for the DQL application, handling:
    - User lifecycle (authentication, registration, deletion).
    - Data management (multi-turn chat history, persistent documents).
    - Configuration (user-specific DQL language settings).
    - Performance optimization via a multi-tiered caching system with automatic invalidation.

    Attributes:
        EMAIL_PATTERN (str): Regex for email validation.
        PASSWORD_PATTERN (str): Regex for strong password enforcement.
    """

    # --- Initialization ---

    # Load environmental variables from the .env file
    load_dotenv()

    _instance = None
    _lock = threading.Lock()

    # Validation patterns
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    PASSWORD_PATTERN = r'^(?=(.*[a-z]){1,})(?=(.*[A-Z]){1,})(?=(.*[0-9]){1,})(?=(.*[!@#$%^&*()\-__+.]){1,}).{8,}$'

    def __init__(self, uri_db: str, project_root: Optional[Path] = None):
        """
        Initialize the MongoDB client, collections, and internal caches.
        Private constructor to be invoked through get_instance().

        Args:
            uri_db (str | None): MongoDB connection string.
            project_root (Path, optional): Root directory for file-based fallbacks.
        """
        if getattr(self, "_initialized", False):
            return

        self._project_root = project_root if project_root else Path(__file__).resolve().parent.parent
        self._file_handler = FileHandler()

        # Resolve URI from arguments or environment
        mongo_uri = self._load_data(uri_db)

        # Establish DB connection and define main collections
        client = MongoClient(mongo_uri)
        db = client["auth_db"]
        self._users = db["users"]
        self._documents = db["documents"]
        self._document_items = db["document_items"]

        # Enforce unique constraints on usernames for integrity
        self._users.create_index("username", unique=True)
        self._documents.create_index("username", unique=True)
        self._document_items.create_index("username")
        self._document_items.create_index([("username", 1), ("doc_id", 1)], unique=True)
        self._document_items.create_index([("username", 1), ("persisted_doc.type_doc", 1)])

        # Audit collection for tracking individual user queries
        self._questions = db["user_questions"]

        # -------------------------------
        # --- Battle votes collection ---
        # -------------------------------
        self._battle_votes = db["battle_votes"]
        # Indexes speed up dashboards and prevent duplicate votes during upsert.
        self._battle_votes.create_index("battle_id")
        self._battle_votes.create_index([("user", 1), ("battle_id", 1)], unique=True)
        self._battle_votes.create_index("chosen_model")
        self._battle_votes.create_index([("timestamp", -1)])
        # Mode index supports quick filtering between anonymous and labeled battles.
        self._battle_votes.create_index([("mode", 1)])

        # --- Memory Caching Layer ---
        # Separated caches to minimize lock contention during parallel access
        self._chat_cache: Dict[str, Dict[str, List[dict]]] = {}
        self._lang_cache: Dict[str, dict] = {}
        self._docs_cache: Dict[str, List[dict]] = {}

        self._chat_cache_lock = threading.Lock()
        self._lang_cache_lock = threading.Lock()
        self._docs_cache_lock = threading.Lock()

        self._initialized = True

    @classmethod
    def get_instance(cls, uri_db: str = None, project_root: Optional[Path] = None) -> "Storage":
        """
        Provides thread-safe access to the Storage singleton.

        Args:
            uri_db (str): Mongo URI (required only for initial creation).
            project_root (Path): Root path (required only for initial creation).

        Returns:
            Storage: The initialized singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(uri_db, project_root)
        return cls._instance

    # ------------------------------
    # --- Initialization Helpers ---
    # ------------------------------

    def _load_data(self, value: Optional[str], env_var: str = "MONGO_URI") -> str:
        """
        Prioritizes credential loading from direct input, then system environment.
        """
        if value:
            return value

        env_value = os.getenv(env_var)
        if env_value:
            return env_value

        raise ValueError(f"CRITICAL: Failed to load MongoDB connection string from '{env_var}'.")

    # ----------------------
    # --- Authentication ---
    # ----------------------

    def register_user(self, username: str, email: str, password: str, role="Altro") -> Tuple[bool, Any]:
        """
        Creates a new user profile, enforces security policies, and prepares
        default environment (documents/settings).
        """
        username = username.strip()
        email = email.strip()

        # Block reserved administrative keywords
        if username in ["vitali", "salomone"]:
            return False, "Username/Email non disponibili"

        # Uniqueness check for credentials
        if self._users.find_one({"username": username}) or self._users.find_one({"email": email}):
            return False, "Username/Email non disponibili"

        # Format and strength validation
        if not re.fullmatch(self.EMAIL_PATTERN, email):
            return False, "Formato Email non valido"
        elif not re.match(self.PASSWORD_PATTERN, password):
            return False, "La password deve avere almeno 8 caratteri, con 1 minuscola, 1 maiuscola, 1 numero e 1 simbolo speciale (!@#$%^&*()-_+.)"
        elif role not in ["Giudice", "Avvocato", "Admin", "Altro"]:
            return self.register_user(username, email, password, "Altro")

        # Secure password hashing with Salt
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            # Construct the comprehensive user document
            new_user = {
                "_id": ObjectId(),
                "username": username,
                "email": email,
                "password": hashed_pw,
                "role": role,
                "data": {"chat": {}},
                "settings": {"language": self._get_default_language(username)}
            }

            self._users.insert_one(new_user)

            # Populate document collection with shared and user-private files
            self._register_documents("vitali")
            self._register_documents("salomone")
            self._register_documents(username)

            return True, new_user
        except Exception as e:
            return False, str(e)

    def _register_documents(self, username: str):
        """
        Helper method to initialize the 'documents' collection for a user.
        Injects relevant files from the project static directory.
        """
        if not self._documents.find_one({"username": username}):
            try:
                new_doc_entry = {
                    "_id": ObjectId(),
                    "username": username,
                    "data": {"persisted_docs": []}
                }
                self._documents.insert_one(new_doc_entry)
                self._invalidate_cache(username, self._docs_cache, self._docs_cache_lock)
            except Exception:
                pass

        for doc in self._get_default_docs(username):
            self.upload_document(username, doc)

    def upload_document(self, username: str, persisted_doc, file_name=None) -> bool:
        """
        Inserts a document into the user's document collection.
        Returns True if successful, False otherwise.
        """
        if not isinstance(persisted_doc, dict):
            persisted_doc = {"text": str(persisted_doc)}
        elif "text" not in persisted_doc:
            persisted_doc["text"] = str(persisted_doc)

        if "_id" not in persisted_doc:
            stable_id = persisted_doc.get("name") or persisted_doc.get("type_doc")
            persisted_doc["_id"] = str(stable_id) if stable_id else str(ObjectId())

        if "type_doc" not in persisted_doc:
            persisted_doc["type_doc"] = "UNKNOWN"

        if "name" not in persisted_doc and file_name:
            persisted_doc["name"] = file_name

        if "owner" not in persisted_doc:
            persisted_doc["owner"] = username

        try:
            result = self._document_items.update_one(
                {"username": username, "doc_id": str(persisted_doc["_id"])},
                {"$setOnInsert": {"persisted_doc": persisted_doc}},
                upsert=True
            )

            self._invalidate_cache(username, self._docs_cache, self._docs_cache_lock)

            return bool(result.upserted_id) or result.matched_count > 0
        except Exception as e:
            print(f"Upload document failed: {e}")
            return False

    def delete_document(self, username: str, doc_id: str) -> bool:
        """
        Removes a document from the user's document collection by its unique ID.
        """
        try:
            item_result = self._document_items.delete_one(
                {"username": username, "doc_id": str(doc_id)}
            )

            deleted = item_result.deleted_count > 0

            if not deleted:
                result = self._documents.update_one(
                    {"username": username},
                    {"$pull": {"data.persisted_docs": {"_id": doc_id}}}
                )
                deleted = result.modified_count > 0

            self._invalidate_cache(username, self._docs_cache, self._docs_cache_lock)

            return deleted
        except Exception as e:
            print(f"Delete document failed: {e}")
            return False

    def login_user(self, username, password) -> Tuple[bool, Optional[dict]]:
        """
        Validates login attempts by comparing hashes.
        """
        user = self._users.find_one({"username": username})

        if not user:
            return False, None

        # Verification using bcrypt to prevent timing attacks
        if bcrypt.checkpw(password.encode("utf-8"), user.get("password", b"")):
            return True, user

        return False, None

    def get_all_users(self) -> List[dict]:
        """
        Fetches all registered users while stripping sensitive password hashes.
        """
        return list(self._users.find({}, {"password": 0}))

    def delete_user(self, user_id: str) -> bool:
        """
        Wipes a user record, their associated documents, and clears all internal caches.
        """
        self._documents.delete_one({"username": user_id})
        self._document_items.delete_many({"username": user_id})
        result = self._users.delete_one({"username": user_id})

        # Consistency: ensure stale data is removed from memory
        if result.deleted_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)
            self._invalidate_cache(user_id, self._docs_cache, self._docs_cache_lock)
            self._invalidate_cache(user_id, self._lang_cache, self._lang_cache_lock)

        return result.deleted_count > 0

    # ---------------------------
    # --- Document Operations ---
    # ---------------------------

    def _get_document(self, user_id: str, key: tuple, value: str) -> Optional[dict]:
        """
        Searches for a specific document inside arrays, automatically
        selecting the correct collection (users vs documents).
        """
        if key[0] == "persisted_docs":
            item = self._document_items.find_one(
                {"username": user_id, f"persisted_doc.{key[1]}": value},
                {"persisted_doc": 1, "_id": 0}
            )
            if item and "persisted_doc" in item:
                return item["persisted_doc"]

        # Determine source collection based on the data key
        collection = self._documents if key[0] == "persisted_docs" else self._users

        # Positional matching via MongoDB Projection
        query_key = f"data.{key[0]}.{key[1]}"
        projection = {f"data.{key[0]}.$": 1, "_id": 0}

        result = collection.find_one(
            {"username": user_id, query_key: value},
            projection
        )

        if result and "data" in result and key[0] in result["data"]:
            return result["data"][key[0]][0]
        return None

    def get_all_documents(self, user_id: str) -> Optional[List[dict]]:
        """
        Retrieves the user's document list with cache-first lookup.
        """
        with self._docs_cache_lock:
            if user_id in self._docs_cache:
                return self._docs_cache[user_id]

        item_docs = list(
            self._document_items.find(
                {"username": user_id},
                {"persisted_doc": 1, "_id": 0}
            )
        )

        if item_docs:
            docs = [d.get("persisted_doc") for d in item_docs if d.get("persisted_doc") is not None]
            with self._docs_cache_lock:
                self._docs_cache[user_id] = docs
            return docs

        return self._get_cached_data(
            user_id,
            self._docs_cache,
            self._docs_cache_lock,
            {"data.persisted_docs": 1, "_id": 0},
            ["data", "persisted_docs"],
            collection=self._documents
        )

    def get_document_by_type(self, user_id: str, value: str) -> Optional[dict]:
        """Retrieves a document filtered by its functional type."""
        docs = self.get_all_documents(user_id)
        value = value.lower()
        if not docs:
            return []
        return [doc for doc in docs if (doc.get("type_doc") or "").lower() == value]

    def get_document_by_name(self, user_id: str, value: str) -> Optional[dict]:
        """Retrieves a document filtered by its filename/name."""
        docs = self.get_all_documents(user_id)
        value = value.lower()
        if not docs:
            return []
        return [doc for doc in docs if (doc.get("name") or "").lower() == value]

    def _get_default_docs(self, username: str) -> list:
        """Loads base JSON documents from the local filesystem."""
        doc_path = os.path.join(self._project_root, "documents", "corpus", username)
        
        if not os.path.exists(doc_path):
            return []
        
        all_docs =[
            self._file_handler.read_file(os.path.join(doc_path, f))
            for f in os.listdir(doc_path) if f.endswith(".json")
        ]
        
        return [doc for doc in all_docs if doc.get("owner", "") == username]

    def upsert_persisted_doc(self, user_id: str, doc: dict) -> bool:
        """Updates an existing document or pushes a new one if not found."""
        if "type_doc" not in doc:
            raise ValueError("Missing 'type_doc' in document schema.")

        doc.setdefault("updated_at", datetime.utcnow())
        doc_type = doc["type_doc"]

        # Phase 1: Try to update an existing item document by type
        result = self._document_items.update_one(
            {"username": user_id, "persisted_doc.type_doc": doc_type},
            {"$set": {"persisted_doc": doc}}
        )

        # Phase 2: If no entry existed, append to the array
        if result.matched_count == 0:
            if "_id" not in doc:
                stable_id = doc.get("name") or doc.get("type_doc")
                doc["_id"] = str(stable_id) if stable_id else str(ObjectId())

            result = self._document_items.update_one(
                {"username": user_id, "doc_id": str(doc["_id"])},
                {"$setOnInsert": {"persisted_doc": doc}},
                upsert=True
            )

        # Clear cache to reflect the new state in the next read
        if result.modified_count > 0 or result.matched_count > 0:
            self._invalidate_cache(user_id, self._docs_cache, self._docs_cache_lock)

        return result.modified_count > 0 or bool(result.upserted_id)

    # --------------------------------
    # --- Cache Helper Methods ---
    # --------------------------------

    def _invalidate_cache(self, user_id: str, cache: dict, lock: threading.Lock):
        """Removes a user's entry from a specified cache dictionary using thread-locks."""
        with lock:
            if user_id in cache:
                del cache[user_id]

    def _get_cached_data(
        self,
        user_id: str,
        cache: dict,
        lock: threading.Lock,
        projection: dict,
        data_path: List[str],
        collection: Any = None
    ) -> Optional[Any]:
        """Generic template for cache-first data retrieval from MongoDB."""
        # 1. Memory Check
        with lock:
            if user_id in cache:
                return cache[user_id]

        coll = collection if collection is not None else self._users

        # 2. Database Fetch
        result = coll.find_one({"username": user_id}, projection)

        # 3. Path Traversal logic (e.g., result['data']['chat'])
        data = None
        if result:
            temp_data = result
            try:
                for key in data_path:
                    temp_data = temp_data[key]
                data = temp_data
            except KeyError:
                data = None

        # 4. Synchronize Cache
        with lock:
            if data is not None:
                cache[user_id] = data

        return data

    # -----------------------
    # --- Chat Operations ---
    # -----------------------

    def get_all_chats(self, user_id: str) -> Optional[Dict[str, List[dict]]]:
        """Returns the complete mapping of chat conversations for a user."""
        return self._get_cached_data(
            user_id,
            self._chat_cache,
            self._chat_cache_lock,
            {"data.chat": 1, "_id": 0},
            ["data", "chat"]
        )

    def get_chat_messages(self, user_id: str, chat_id: str) -> List[dict]:
        """Extracts the message array for a specific conversation ID."""
        chat_history = self.get_all_chats(user_id)
        if chat_history is None:
            return []
        return chat_history.get(chat_id, [])

    def get_message(self, user_id: str, chat_id: str, message_id: str) -> Optional[dict]:
        """Finds a specific message by ID within a given chat session."""
        chat_history = self.get_chat_messages(user_id, chat_id)
        for chat in chat_history:
            if chat.get("id", "").lower() == message_id.lower():
                return deepcopy(chat)
        return None

    def add_chat_message(self, user_id: str, chat_id: str, message: dict) -> bool:
        """Appends a single message to a chat and invalidates the session cache."""
        message.setdefault("timestamp", datetime.utcnow())
        update_field = f"data.chat.{chat_id}"

        result = self._users.update_one(
            {"username": user_id},
            {"$push": {update_field: message}}
        )

        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)

        return result.modified_count > 0

    def replace_chat_messages(self, user_id: str, chat_id: str, messages: List[dict]) -> bool:
        """Fully replaces a chat's history. Also used for initializing new chats."""
        update_field = f"data.chat.{chat_id}"
        result = self._users.update_one(
            {"username": user_id},
            {"$set": {update_field: messages}}
        )

        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)

        return result.modified_count > 0

    def create_new_chat(self, user_id: str) -> Optional[str]:
        """Generates a unique numeric chat ID based on current time and clears empty turns."""
        new_chat_id = re.sub(r"[^0-9]", "", str(datetime.now().isoformat()))
        if self.replace_chat_messages(user_id, new_chat_id, []):
            self._clean_chats(user_id, [new_chat_id])
            return new_chat_id
        return None

    def _clean_chats(self, user_id: str, exceptions: List[str] = []) -> None:
        """Maintenance task: removes empty or single-message chat sessions."""
        all_chats = deepcopy(self.get_all_chats(user_id)) or {}
        for chat in all_chats.keys():
            if chat not in exceptions and len(all_chats.get(chat, [])) < 2:
                self.delete_chat(user_id, chat)

    def delete_chat(self, user_id: str, chat_id: str) -> bool:
        """Permanently removes a chat session field using MongoDB $unset."""
        unset_field = f"data.chat.{chat_id}"
        result = self._users.update_one(
            {"username": user_id},
            {"$unset": {unset_field: ""}}
        )

        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._chat_cache, self._chat_cache_lock)

        return result.modified_count > 0

    # ------------------------------
    # --- User Questions Logging ---
    # ------------------------------

    def log_user_question(self, user_id: str, question: str, model: str,
                          timestamp: Optional[datetime] = None) -> None:
        """Records a user query in a flat audit collection for tracking."""
        doc = {
            "user": user_id,
            "timestamp": timestamp or datetime.utcnow(),
            "question": question,
            "model": model,
        }
        try:
            self._questions.insert_one(doc)
        except Exception as e:
            print(f"[WARN] Storage audit log failed: {e}")

    # ------------------------------
    # --- Battle Votes Logging ---
    # ------------------------------

    def log_battle_vote(
        self,
        user_id: str,
        chat_id: str,
        battle_id: str,
        prompt: str,
        mode: str,               # "anon" | "labeled"
        model_a: str,
        model_b: str,
        chosen_model: str,       # es. "GPT" / "DQL" / "NotebookLM"
        chosen_side: str,        # "A" | "B"
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Save a user's Battle vote with one record per user and battle.

        The upsert prevents duplicates during Streamlit reruns and updates the
        existing record if the user changes their choice.
        """
        ts = timestamp or datetime.utcnow()

        doc = {
            "user": user_id,
            "chat_id": chat_id,
            "battle_id": battle_id,
            "prompt": prompt,
            "mode": mode,
            "model_a": model_a,
            "model_b": model_b,
            "chosen_model": chosen_model,
            "chosen_side": chosen_side,
            "timestamp": ts,
        }

        try:
            self._battle_votes.update_one(
                {"user": user_id, "battle_id": battle_id},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            print(f"[WARN] log_battle_vote failed: {e}")

    def get_battle_scores(self, user_id: Optional[str] = None) -> List[dict]:
        """
        Return aggregated win counts per model.

        Args:
            user_id: Optional filter for one user. If None, returns global scores.

        Returns:
            List[dict]: [{"model": "GPT", "score": 10}, ...] sorted descending.
        """
        pipeline = []
        if user_id:
            pipeline.append({"$match": {"user": user_id}})

        pipeline.extend([
            {"$group": {"_id": "$chosen_model", "score": {"$sum": 1}}},
            {"$sort": {"score": -1}}
        ])

        try:
            res = list(self._battle_votes.aggregate(pipeline))
            return [{"model": r["_id"], "score": r["score"]} for r in res]
        except Exception as e:
            print(f"[WARN] get_battle_scores failed: {e}")
            return []

    def get_battle_results(
        self,
        user_id: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 200
    ) -> List[dict]:
        """
        Return recent Battle vote events.

        Args:
            user_id: Optional user filter.
            mode: Optional battle mode filter: "anon", "labeled", or None.
            limit: Maximum number of events to return.
        """
        query: Dict[str, Any] = {}
        if user_id:
            query["user"] = user_id
        if mode:
            query["mode"] = mode

        try:
            cursor = self._battle_votes.find(query, {"_id": 0}).sort("timestamp", -1).limit(int(limit))
            return list(cursor)
        except Exception as e:
            print(f"[WARN] get_battle_results failed: {e}")
            return []

    # Full score summary with wins, losses, matches, and win rate.
    def get_battle_scores_summary(
        self,
        user_id: Optional[str] = None,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate complete Battle statistics per model.

        Args:
            user_id: Optional user filter.
            mode: Optional battle mode filter: "anon", "labeled", or None.
        """
        query: Dict[str, Any] = {}
        if user_id:
            query["user"] = user_id
        if mode:
            query["mode"] = mode

        by_model: Dict[str, Dict[str, int]] = {}
        total_matches = 0

        try:
            cursor = self._battle_votes.find(
                query,
                {"_id": 0, "model_a": 1, "model_b": 1, "chosen_model": 1}
            )

            for doc in cursor:
                a = doc.get("model_a")
                b = doc.get("model_b")
                winner = doc.get("chosen_model")

                if not a or not b or not winner:
                    continue

                loser = b if winner == a else a

                # Ensure both models have a statistics bucket.
                for m in (a, b):
                    by_model.setdefault(m, {"wins": 0, "losses": 0, "matches": 0})

                # Each vote counts as one match for both participating models.
                by_model[a]["matches"] += 1
                by_model[b]["matches"] += 1

                # Record the selected winner and inferred loser.
                by_model[winner]["wins"] += 1
                by_model[loser]["losses"] += 1

                total_matches += 1

        except Exception as e:
            print(f"[WARN] get_battle_scores_summary failed: {e}")
            return {"by_model": {}, "total_matches": 0}

        # Derive the win rate after all counts are complete.
        for m, stats in by_model.items():
            matches = stats.get("matches", 0) or 0
            wins = stats.get("wins", 0) or 0
            stats["win_rate"] = (wins / matches) if matches > 0 else 0.0

        return {"by_model": by_model, "total_matches": total_matches}

    # ---------------------------
    # --- Language Operations ---
    # ---------------------------

    def get_language(self, user_id: str) -> Optional[dict]:
        """Retrieves user-specific DQL language settings using cache-first strategy."""
        return self._get_cached_data(
            user_id,
            self._lang_cache,
            self._lang_cache_lock,
            {"settings.language": 1, "_id": 0},
            ["settings", "language"]
        )

    def _set_element(self, user_id: str, key: Optional[str], value: Any) -> bool:
        """Atomic update of a specific sub-field in language settings."""
        update_field = f"settings.language.{key}" if key else "settings.language"
        result = self._users.update_one(
            {"username": user_id},
            {"$set": {update_field: value}}
        )

        if result.modified_count > 0:
            self._invalidate_cache(user_id, self._lang_cache, self._lang_cache_lock)

        return result.modified_count > 0

    def set_language(self, user_id: str, language: dict) -> bool:
        """Overwrites the entire language configuration."""
        return self._set_element(user_id, None, language)

    def set_commands(self, user_id: str, commands: List[dict]) -> bool:
        """Updates the available DQL command set."""
        return self._set_element(user_id, "commands", commands)

    def set_sources(self, user_id: str, sources: List[dict]) -> bool:
        """Updates the available document sources grammar."""
        return self._set_element(user_id, "sources", sources)

    def set_what(self, user_id: str, what: List[dict]) -> bool:
        """Updates the 'what' parameters (entities/sections)."""
        return self._set_element(user_id, "what", what)

    def set_default_language(self, user_id: str) -> bool:
        """Resets language settings to system factory defaults."""
        return self.set_language(user_id, self._get_default_language(user_id))

    def _get_default_language(self, username) -> dict:
        """Loads the factory default language JSON from disk."""
        path = os.path.join(self._project_root, "documents", "language", f"{username.lower()}_language.json")
        
        print(f"Loading default language for '{username}' from path: {path}")
        
        if not os.path.exists(path):
            path = os.path.join(self._project_root, "documents", "language", "ldql_language.json")
            
        print(f"Default language path resolved to: {path}")
            
        return self._file_handler.read_file(path)
