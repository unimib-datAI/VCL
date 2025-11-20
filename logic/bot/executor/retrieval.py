"""
Retrieval module responsible for fetching documents required by operations.

Responsibilities:
-----------------
- Retrieve documents from multiple sources in priority order:
    1. Operations list (previously computed results)
    2. MongoDB storage (user/session-scoped cached documents)
    3. Local filesystem (fallback under `documents/` directory)
    4. ElasticSearch (if configured)
- Structured logging for each retrieval attempt and outcome.

Dependencies:
-------------
- utils.config.Config: Provides shared logger, MongoDB storage instance, and DB URL.
- utils.file_manager.FileHandler: Utility for reading JSON/text files.
- elasticsearch.Elasticsearch: Backend for document search.
"""

import os
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    RequestError, NotFoundError, ConnectionError, ConnectionTimeout,
    TransportError, AuthenticationException, AuthorizationException, ApiError
)

from utils.config import Config
from utils.file_manager import FileHandler


class Retrieval:
    """
    Responsible for retrieving documents needed by operations.

    This class follows a chain-of-responsibility pattern, attempting to
    find a document from the fastest/most-specific source (previous
    operation results) to the most general (Elasticsearch).

    Attributes:
        _client (Elasticsearch): Elasticsearch client instance.
        _storage: MongoDB-based storage instance from Config.
        _rag (bool): Flag for RAG (Retrieval-Augmented Generation) mode.
        _logger: Logger instance from Config.
        _project_root (str): Root project path for local file fallback.
        _user_id (str): User/session identifier for scoped retrieval.
        _operations (list[dict]): Optional list of operation results.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config, operations: list[dict] = None):
        """
        Initialize the Retrieval component.

        Args:
            cfg (Config): The global configuration object.
            operations (list[dict], optional): A list of previously
                executed operations in the current pipeline, used to
                retrieve intermediate results.
        """
        self._client = Elasticsearch(cfg.DB_URL)
        self._storage = cfg.storage
        self._user_id = cfg.get_user_id()
        self._operations = operations or []
        self._project_root = cfg.project_root
        self._logger = cfg.get_logger("Retrieval")

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def execute(self, operation: dict) -> list[dict]:
        """
        Retrieve all documents specified in the operation's 'from' field.

        Retrieval priority:
            1. Operations list (intermediate results)
            2. MongoDB storage (session cache)
            3. Local filesystem (static documents)
            4. ElasticSearch (general document database)

        Args:
            operation (dict): An operation in DQL format.

        Returns:
            list[dict]: A list of retrieved documents. Each document is a
                        dict with 'name', 'text', and 'type'.
        """
        retrieved_docs = []

        for doc_name in operation.get("from", []):
            doc = self._retrieve_document(doc_name)
            retrieved_docs.append(doc)

        return retrieved_docs

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _retrieve_document(self, doc_name: str) -> dict:
        """
        Attempt to retrieve a single document from multiple sources
        in priority order.

        Args:
            doc_name (str): Name, ID, or type of document to retrieve.

        Returns:
            dict: Retrieved document with 'name', 'text', 'type'.
        """
        # Define the retrieval strategies in order of priority.
        retrieval_methods = [
            ("Operations List", self._get_from_operations_list),
            ("MongoDB", self._get_from_mongo),
            ("LocalSystem", self._get_from_local_system),
            ("ElasticSearch", self._get_from_elastic_search)
        ]

        for label, method in retrieval_methods:
            self._logger.info(f"Attempting to retrieve '{doc_name}' via {label}...")
            doc = method(doc_name)
            if doc:
                self._logger.info(f"Document '{doc_name}' successfully retrieved from {label}.")
                return doc
            self._logger.info(f"'{doc_name}' not found in {label}.")

        # Fallback: If no document is found, treat the input
        # string 'doc_name' as raw text content.
        self._logger.warning(f"'{doc_name}' not found in any source. Treating as raw text input.")
        return {"name": f"doc_{doc_name}", "text": doc_name, "type": "text"}

    def _get_from_operations_list(self, doc_name: str) -> dict | None:
        """Retrieve document from previously computed operations."""
        for op in self._operations:
            # Check if an operation ID matches and has a result
            if op.get("id") == doc_name and "result" in op and op.get("from"):
                # The 'type' is inferred from the source of the previous operation
                return {"name": doc_name, "text": op["result"], "type": op["from"][0]}
        return None

    def _get_from_mongo(self, doc_name: str) -> dict | None:
        """Retrieve document from MongoDB storage scoped by user/session."""
        # Try retrieving by type, then ID, then name
        for method in [self._storage.get_document_by_type,
                           #self._storage.get_document_by_id,
                           self._storage.get_document_by_name]:
            doc = method(self._user_id, doc_name)
            if doc and "text" in doc:
                return {"name": doc["name"], "text": doc["text"], "type": doc_name}
        return None

    def _get_from_local_system(self, doc_name: str) -> dict | None:
        """Retrieve document from local filesystem under 'documents/' directory."""
        folder = os.path.join(self._project_root, "documents")
        handler = FileHandler()

        try:
            for fname in os.listdir(folder):
                if not fname.endswith(".json"):
                    continue
                try:
                    path_file = os.path.join(folder, fname)
                    doc = handler.read_file(path_file)

                    # Match by 'name' or 'type_doc' field in the JSON
                    if doc.get("name") == doc_name or doc.get("type_doc") == doc_name:
                        return {
                            "name": doc.get("name", ""),
                            "text": doc.get("text", ""),
                            "type": doc.get("type_doc", "task"),
                        }
                except Exception as e:
                    self._logger.warning(f"Error reading local file '{fname}': {e}")
        except FileNotFoundError:
            self._logger.warning(f"Local documents directory not found at: {folder}")
        except Exception as e:
            self._logger.error(f"Failed to scan local document directory: {e}")
            
        return None

    def _get_from_elastic_search(self, doc_name: str) -> dict | None:
        """
        Attempt to retrieve a document by type from ElasticSearch.

        Args:
            doc_name (str): Document type to search for.

        Returns:
            dict | None: Document if found, else None.
        """
        # Assumes doc_name is a 'type_doc' for this query
        query = {"query": {"bool": {"must": [{"match": {"type_doc": doc_name}}]}}}

        try:
            response = self._client.search(index="sperimentazione", body=query)
            # Return the first valid hit
            for hit in response.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                if "name" in src and "text" in src:
                    return {"name": src["name"], "text": src["text"], "type": doc_name}

        except (NotFoundError, RequestError, AuthenticationException,
                AuthorizationException, ConnectionTimeout, ConnectionError,
                TransportError, ApiError) as e:
            # Specific, common ES errors
            self._logger.warning(f"ElasticSearch retrieval failed for '{doc_name}': {e}")
        except Exception as e:
            # Catch-all for unexpected errors
            self._logger.exception(f"Unexpected error retrieving '{doc_name}' from ElasticSearch: {e}")

        return None