"""
Retrieval module responsible for fetching documents required by operations.

Responsibilities:
-----------------
- Retrieve documents from multiple sources in priority order:
    1. Operations list (previously computed results)
    2. Redis storage (user/session-scoped cached documents)
    3. Local filesystem (fallback under `documents/` directory)
    4. ElasticSearch (if RAG enabled)
- Structured logging for each retrieval attempt and outcome.

Dependencies:
-------------
- utils.config.Config: Provides shared logger, Redis storage instance, and DB URL.
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

    Attributes:
        client (Elasticsearch): Elasticsearch client instance.
        storage: Redis-based storage instance from Config.
        rag (bool): Flag for RAG (Retrieval-Augmented Generation) mode.
        logger: Logger instance from Config.
        project_root (str): Root project path for local file fallback.
        id_user (str): User/session identifier for scoped retrieval.
        operations (list[dict]): Optional list of operation results.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config, operations: list[dict] = None):
        self.client = Elasticsearch(cfg.DB_URL)
        self.storage = cfg.storage
        self.id_user = cfg.user_id
        self.operations = operations or []
        self.project_root = cfg.project_root
        self.logger = cfg.get_logger("Retrieval")

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def execute(self, operation: dict) -> list[dict]:
        """
        Retrieve documents for the given operation.

        Retrieval priority:
            1. Operations list
            2. Redis storage
            3. Local filesystem
            4. ElasticSearch

        Args:
            operation (dict): Operation in DQL language.

        Returns:
            list[dict]: Retrieved documents with keys 'name', 'text', and 'type'.
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
        Attempt to retrieve a single document from multiple sources in priority order.

        Args:
            doc_name (str): Name or type of document to retrieve.

        Returns:
            dict: Retrieved document with 'name', 'text', 'type'.
        """
        retrieval_methods = [
            ("Operations List", self._get_from_operations_list),
            ("Redis", self._get_from_redis),
            ("LocalSystem", self._get_from_local_system),
            ("ElasticSearch", self._get_from_elastic_search)
        ]

        for label, method in retrieval_methods:
            self.logger.info(f"Attempting to retrieve '{doc_name}' via {label}...")
            doc = method(doc_name)
            if doc:
                self.logger.info(f"Document '{doc_name}' successfully retrieved from {label}.")
                return doc
            self.logger.info(f"'{doc_name}' not found in {label}.")

        # Fallback: treat input string as raw text
        self.logger.warning(f"'{doc_name}' treated as raw text input.")
        return {"name": f"doc_{doc_name}", "text": doc_name, "type": "text"}

    def _get_from_operations_list(self, doc_name: str) -> dict | None:
        """Retrieve document from previously computed operations."""
        for op in self.operations:
            if op.get("id") == doc_name and "result" in op and op.get("from"):
                return {"name": doc_name, "text": op["result"], "type": op["from"][0]}
        return None

    def _get_from_redis(self, doc_name: str) -> dict | None:
        """Retrieve document from Redis storage scoped by user/session."""
        for method in [self.storage.get_documents_by_type,
                       self.storage.get_documents_by_id,
                       self.storage.get_documents_by_name]:
            doc = method(doc_name)
            if doc and "text" in doc:
                return {"name": doc["name"], "text": doc["text"], "type": doc_name}
        return None

    def _get_from_local_system(self, doc_name: str) -> dict | None:
        """Retrieve document from local filesystem under 'documents/' directory."""
        folder = os.path.join(self.project_root, "documents")
        handler = FileHandler()

        for fname in os.listdir(folder):
            if not fname.endswith(".json"):
                continue
            try:
                path_file = os.path.join(folder, fname)
                doc = handler.read_file(path_file)

                if doc.get("name") == doc_name or doc.get("type_doc") == doc_name:
                    return {
                        "name": doc.get("name", ""),
                        "text": doc.get("text", ""),
                        "type": doc.get("type_doc", "task"),
                    }
            except Exception as e:
                self.logger.warning(f"Error reading '{fname}': {e}")
        return None

    def _get_from_elastic_search(self, doc_type: str) -> dict | None:
        """
        Attempt to retrieve a document by type from ElasticSearch.

        Args:
            doc_type (str): Document type to search for.

        Returns:
            dict | None: Document if found, else None.
        """
        query = {"query": {"bool": {"must": [{"match": {"type_doc": doc_type}}]}}}

        try:
            response = self.client.search(index="sperimentazione", body=query)
            for hit in response.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                if "name" in src and "text" in src:
                    return {"name": src["name"], "text": src["text"], "type": doc_type}

        except (NotFoundError, RequestError, AuthenticationException,
                AuthorizationException, ConnectionTimeout, ConnectionError,
                TransportError, ApiError) as e:
            self.logger.warning(f"ElasticSearch retrieval failed for '{doc_type}': {e}")
        except Exception as e:
            self.logger.exception(f"Unexpected error retrieving '{doc_type}' from ElasticSearch: {e}")

        return None
