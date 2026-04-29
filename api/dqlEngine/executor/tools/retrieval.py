"""Document retrieval helpers for MongoDB, local files, and prior operations."""

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
    Core retrieval engine responsible for fetching documents across multiple storage layers.

    This class implements a multi-tiered retrieval strategy (Chain of Responsibility), 
    attempting to find documents starting from the most volatile/specific source 
    (in-memory operation results) to the most persistent/general source (Elasticsearch).

    Responsibilities:
        - Resolving document references from previous pipeline steps.
        - Fetching user-scoped documents from MongoDB.
        - Accessing static files from the local filesystem.
        - Performing indexed searches via Elasticsearch.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config, operations: list[dict] = None, user_id: str = None, chat_id: str = None, sources_id: str = None):
        """
        Initialize the Retrieval component with global configuration.

        Args:
            cfg (Config): Global configuration instance providing DB connections and loggers.
            operations (list[dict], optional): Results from previously executed 
                operations in the current session, enabling cross-task references.
        """
        # self._client = Elasticsearch(cfg.DB_URL)
        self._storage = cfg.get_storage()
        self._user_id = user_id
        self._chat_id = chat_id
        self._sources_id = sources_id
        self._operations = operations or []
        self._project_root = cfg.project_root
        self.get_logger = cfg.get_logger

    # ----------------------
    # --- Public Methods ---
    # ----------------------
    
    def execute(self, operation: dict, request_id: str = None) -> list[dict]:
        """
        Resolves all document dependencies listed in the 'from' field of an operation.

        Args:
            operation (dict): A structured DQL operation dictionary.
            request_id (str, optional): The ID of the current request for logging purposes.

        Returns:
            list[dict]: A list of objects containing 'name', 'text', and 'type' for 
                        every successfully retrieved document.
        """
        self._logger = self.get_logger("Retrieval", request_id)
        
        retrieved_docs = []

        # Iterate through all identifiers in the 'from' clause
        for doc_name in operation.get("from", []):
            retrieved_docs.extend(self._retrieve_document(doc_name))
                
        print(len(retrieved_docs))

        return retrieved_docs

    # ------------------------------
    # --- Private Helper Methods ---
    # ------------------------------
    
    def _retrieve_document(self, doc_name: str) -> dict:
        """
        Internal dispatcher that attempts retrieval through the defined hierarchy.

        Retrieval Priority:
            1. Operations List (Internal state)
            2. MongoDB Documents (Session-specific)
            3. MongoDB Chat History (Conversation-specific)
            4. Local Filesystem (Static fallback)
            5. Elasticsearch (Global index)

        Args:
            doc_name (str): The unique identifier or type of the document.

        Returns:
            dict: The normalized document dictionary if found; otherwise, 
                  returns the input as raw text.
        """
        self._logger.info(f"Current Use Case Context: {self._sources_id}")
        
        # Define the ordered sequence of retrieval strategies
        retrieval_methods = [
            ("Operations List", self._get_from_operations_list),
            ("MongoDB (DOC)", self._get_doc_from_mongo),
            ("MongoDB (CHAT)", self._get_chat_from_mongo),
            ("LocalSystem", self._get_from_local_system),
            # ("ElasticSearch", self._get_from_elastic_search)
        ]

        for label, method in retrieval_methods:
            doc = method(doc_name)
            if len(doc) > 0:
                self._logger.info(f"Document '{doc_name}' successfully retrieved from {label}.")
                return doc

        # Fallback mechanism: If no source contains the ID, treat it as a literal string input
        self._logger.warning(f"'{doc_name}' not found in any source. Casting to raw text document.")
        return [{"name": f"doc_{doc_name}", "text": doc_name, "type": "text"}]

    def _get_from_operations_list(self, doc_name: str) -> list[dict]:
        """
        Checks the internal pipeline state for results from previous tasks.
        Enables the assistant to 'remember' and use data generated earlier in the same request.
        """
        result = []
        
        done = False
        for op in self._operations:
            if op.get("id") == doc_name:
                result.append({"name": doc_name, "text": op.get("result", ""), "type": op.get("structured_prompt", {}).get("from", ["UNKNOWN"])[0]})
                done = True
                
            # Recurse into sub-operations if present
            if "operations" in op:
                for o in op["operations"]:
                    if o.get("id") == doc_name:
                        result.append({"name": doc_name, "text": o.get("result", ""), "type": o.get("structured_prompt", {}).get("from", ["UNKNOWN"])[0]})
                        done = True
            
            if done:
                break
        
        return result

    def _get_doc_from_mongo(self, doc_name: str) -> list[dict]:
        """
        Retrieves user-scoped legal documents from MongoDB.
        Checks both the 'type_doc' and 'name' indices.
        """
        result = []
        # Sequential check: Try matching by document type first, then by filename
        for method in [self._storage.get_document_by_type,
                        self._storage.get_document_by_name]:
            doc = method(self._sources_id, doc_name)
            if doc and "text" in doc:
                result.append({"name": doc["name"], "text": doc["text"], "type": doc_name})
        
        return result
    
    def _get_chat_from_mongo(self, doc_name: str) -> list[dict]:
        """
        Retrieves a specific message from the current chat history in MongoDB.
        Useful when the user refers to a previous answer by its unique ID.
        """
        result = []
        doc = self._storage.get_message(self._user_id, self._chat_id, doc_name)
        
        if doc and "content" in doc:
            result.append({"name": doc["id"], "text": doc["content"], "type": doc_name})
        
        return result

    def _get_from_local_system(self, doc_name: str) -> list[dict]:
        """
        Fallback to the local 'documents/' directory for static JSON files.
        Validates ownership against the current 'sources_id' config.
        """
        result = []
        
        folder = os.path.join(self._project_root, "documents", "corpus", self._sources_id)
        handler = FileHandler()

        try:
            if not os.path.exists(folder):
                self._logger.warning(f"Local document repository not found: {folder}")
                return []
                        
            for fname in os.listdir(folder):
                if not fname.endswith(".json"):
                    continue
                try:
                    path_file = os.path.join(folder, fname)
                    doc = handler.read_file(path_file)

                    # Ownership and name/type validation
                    if (doc.get("name").lower() == doc_name.lower() or doc.get("type_doc").lower() == doc_name.lower()) and doc.get("owner") == self._sources_id:
                        result.append(
                            {
                                "name": doc.get("name", ""),
                                "text": doc.get("text", ""),
                                "type": doc.get("type_doc", "task"),
                            }
                        )
                except Exception as e:
                    self._logger.warning(f"Error parsing local file '{fname}': {e}")
        except FileNotFoundError:
            self._logger.warning(f"Static document repository not found: {folder}")
        except Exception as e:
            self._logger.warning(f"Unexpected error scanning local directory: {e}")
            
        return result

    def _get_from_elastic_search(self, doc_name: str) -> list[dict]:
        """
        Queries the global Elasticsearch index for documents matching the requested type.
        """
        # Search query focused on the 'type_doc' field
        query = {"query": {"bool": {"must": [{"match": {"type_doc": doc_name}}]}}}

        result = []
        
        try:
            response = self._client.search(index="sperimentazione", body=query)
            # Fetch the first relevant hit from the results
            for hit in response.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                if "name" in src and "text" in src:
                    result.append({"name": src["name"], "text": src["text"], "type": doc_name})

        except (NotFoundError, RequestError, AuthenticationException,
                AuthorizationException, ConnectionTimeout, ConnectionError,
                TransportError, ApiError) as e:
            # Handle connectivity and indexing errors gracefully
            self._logger.warning(f"ElasticSearch backend error for '{doc_name}': {e}")
        except Exception as e:
            self._logger.warning(f"Unexpected ES failure for '{doc_name}': {e}")

        return result
