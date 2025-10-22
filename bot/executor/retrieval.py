"""
Retrieval module responsible for fetching documents required by operations.

Main Responsibilities:
-----------------------
- Retrieve documents from multiple sources, in priority order:
  1. ElasticSearch DB.
  2. Redis storage (user/session-scoped cached documents).
  3. Local filesystem (fallback under `documents/` directory).
- Ensure structured logging for each retrieval attempt and outcome.

Dependencies:
-------------
- utils.config.Config: Provides shared logger, Redis storage instance, and DB URL.
- utils.file_manager.read_file: Utility for reading JSON/text files.
- elasticsearch.Elasticsearch: Potential backend for semantic/document search.
"""

import os
import networkx as nx

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    RequestError, NotFoundError, ConnectionError, ConnectionTimeout, 
    TransportError, AuthenticationException, AuthorizationException, ApiError
)

from bot.utils.config import Config
from bot.utils.file_manager import read_file


class Retrieval:
    """
    Class responsible for retrieving documents used by operations.

    Attributes:
        client (Elasticsearch): Elasticsearch client instance (currently unused placeholder).
        storage (Storage): Shared Redis-based storage instance.
        rag (bool): Flag indicating whether RAG (Retrieval-Augmented Generation) mode is enabled.
        logger (logging.Logger): Structured JSON logger instance.
        project_root (str): Root path of the project, used for local fallback.
    """

    def __init__(self, cfg: Config, operations: dict = None):
        self.client = Elasticsearch(cfg.DB_URL)
        self.storage = cfg.storage
        
        self.id_user = cfg.user_id
        self.operations = operations
        
        self.project_root = cfg.project_root
        
        self.logger = cfg.get_logger("Retrieval")
        self.rag = False  # TODO: Switch to cfg.rag when RAG mode is implemented
        

    def execute(self, operation: dict) -> list[dict]:
        """
        Execute document retrieval for the given operation.

        Retrieval priority:
        1. RAG/ElasticSearch retrieval.
        2. Redis storage (session/user-specific).
        3. Local filesystem (`documents/` directory).

        Args:
            operation (dict): Operation object containing a `documents` list of document names.
            id_user (str): User/session identifier for scoping Redis lookups.

        Returns:
            list[dict]: List of retrieved documents with keys:
                - "name" (str): Document name/identifier.
                - "text" (str): Full text content of the document.
                - "type" (str): Type/category of the document.
        """
        docs = []

        if self.rag:
            self.logger.info("RAG mode enabled — retrieval via ElasticSearch or similar not implemented yet.")
            docs = []
        else:
            for doc in operation.get("from", []):
                added = False
                for (label, method) in [("Operations List", self.get_from_operations_list),
                                      ("Redis", self.get_from_redis), 
                                      ("LocalSystem", self.get_from_local_system),
                                      ("ElasticSearch", self.get_from_elastic_search)]:
                    self.logger.info(f"Attempting to retrieve '{doc}' via {label}...")
                    doc_file = method(doc)

                    if doc_file:
                        docs.append(doc_file)
                        added = True
                        self.logger.info(f"Document '{doc}' successfully retrieved from {label}.")
                        break

                    self.logger.info(f"'{doc}' not found in {label}.")

                if not added:
                    docs.append({"name": f"doc_{len(docs)}", "text": doc, "type": "text"})
                    self.logger.warning(f"'{doc}' could be directly the sentence on which to apply the command")

        return docs
    
    def get_from_operations_list(self, doc: str) -> dict | None:
        for op in self.operations:
            if op.get("id", "") == doc and "result" in op:
                return {"name": doc, "text": op.get("result", ""), "type": "operation"}
        return None

    def get_from_elastic_search(self, file_type: str) -> dict | None:
        """
        Attempt to retrieve a document by name from ElasticSearch.

        Args:
            file_name (str): Name of the file/document to retrieve.

        Returns:
            dict | None: Document with fields {"name", "text", "type"} if found, otherwise None.
        """
        try:
            db_query = {
                "query": {
                    "bool": {
                        "must": [{"match": {"type_doc": file_type}}]
                    }
                }
            }

            response = self.client.search(index="sperimentazione", body=db_query)

            for hit in response.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                if "name" in src and "text" in src:
                    return {"name": src["name"], "text": src["text"], "type": file_type}

        except NotFoundError:
            self.logger.debug("ElasticSearch: Index or document not found.")
        except RequestError:
            self.logger.error("ElasticSearch: Malformed query or bad request.")
        except AuthenticationException:
            self.logger.error("ElasticSearch: Authentication failed.")
        except AuthorizationException:
            self.logger.error("ElasticSearch: Insufficient permissions.")
        except ConnectionTimeout:
            self.logger.warning("ElasticSearch: Connection timeout.")
        except ConnectionError:
            self.logger.warning("ElasticSearch: Network connection error.")
        except TransportError:
            self.logger.error("ElasticSearch: Transport layer error.")
        except ApiError:
            self.logger.error("ElasticSearch: General API error.")
        except Exception as e:
            self.logger.exception(f"ElasticSearch: Unexpected error: {e}")

        return None

    def get_from_redis(self, file_type: str) -> dict | None:
        """
        Retrieve a document from Redis cache, scoped by user/session ID.

        Args:
            id_user (str): User/session identifier.
            file_name (str): Document name to retrieve.

        Returns:
            dict | None: Document with {"name", "text", "type"} if found, otherwise None.
        """
        for method in [self.storage.get_element_by_type, self.storage.get_element_by_id, self.storage.get_element_by_name]:
            doc = method(self.id_user, file_type)
            if doc and "text" in doc:
                return {"name": doc["name"], "text": doc["text"], "type": file_type}
        
        return None

    def get_from_local_system(self, file_name: str) -> dict | None:
        path_folder = os.path.join(self.project_root, "documents")

        for fname in os.listdir(path_folder):
            try:
                if not fname.endswith(".json"):
                    continue

                path_file = os.path.join(path_folder, fname)
                doc = read_file(path_file)

                if doc.get("name", "") == file_name:
                    return {
                        "name": doc.get("name", ""),
                        "text": doc.get("text", ""),
                        "type": doc.get("type_doc", "task"),
                    }

                if doc.get("type_doc", "") == file_name:
                    return {
                        "name": doc.get("name", ""),
                        "text": doc.get("text", ""),
                        "type": doc.get("type_doc", "task"),
                    }

            except Exception as e:
                print(f"Errore leggendo {fname}: {e}")
                continue

        return None
            
