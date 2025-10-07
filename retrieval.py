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
import threading

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    RequestError, NotFoundError, ConnectionError, ConnectionTimeout, 
    TransportError, AuthenticationException, AuthorizationException, ApiError
)

from utils.config import Config
from utils.file_manager import read_file


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
    
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    doc_map = {
        "sentenza di primo grado": "S1 - AN",
        "sentenza di secondo grado": "S2 - AN",
        "memoria giudiziale": "M2 - AN",
        "ricorso giudiziale": "R2 - AN",
    }

    def __init__(self, cfg: Config):
        """
        Initialize a new Retrieval instance using shared configuration.

        Args:
            cfg (Config): Shared application configuration instance.
        """
        self.client = Elasticsearch(cfg.DB_URL)
        self.storage = cfg.storage
        self.rag = False  # TODO: Switch to cfg.rag when RAG mode is implemented
        self.logger = cfg.get_logger("Retrieval")
        self.project_root = cfg.project_root
        
    @classmethod
    def get_instance(cls, cfg: Config):
        """
        Retrieve the singleton instance of Config, creating it if necessary.

        Args:
            opts (argparse.Namespace, optional): Parsed command-line options.

        Returns:
            Config: The singleton instance of the configuration.
        """
        if cls._instance is None:
            with cls._lock:  # Ensure thread-safe initialization
                if cls._instance is None:
                    cls._instance = cls(cfg)
        return cls._instance

    def execute(self, operation: dict, id_user: str) -> list[dict]:
        """
        Execute document retrieval for the given operation.

        Retrieval priority:
        1. (Future) RAG/ElasticSearch retrieval (not implemented yet).
        2. Redis storage (session/user-specific).
        3. Local filesystem (`documents/` directory).

        Args:
            operation (dict): Operation object containing a `documents` list of document names.
            id_user (str): User/session identifier for scoping Redis lookups.

        Returns:
            list[dict]: List of retrieved documents with keys:
                - "name" (str): Document name/identifier.
                - "text" (str): Full text content of the document.
        """
        docs = []

        # Placeholder for future RAG/semantic retrieval system
        if self.rag:
            self.logger.info("RAG mode enabled — retrieval via ElasticSearch or similar not implemented yet.")
            docs = []
        else:
            for doc in operation.get("documents", []):
                doc_name = self.doc_map.get(doc, doc)
                
                self.logger.info(f"Attempting to retrieve '{doc_name}' via ElasticSearch...")

                # 1. Try to retrieve from ElasticSearch (currently optional/experimental)
                doc = self.get_from_elastic_search(doc_name)

                if doc:
                    docs.append(doc)
                    self.logger.info(f"Document '{doc_name}' successfully retrieved from ElasticSearch.")
                    continue

                self.logger.info(f"'{doc_name}' not found in ElasticSearch. Trying Redis storage...")

                # 2. Try to retrieve from Redis cache
                doc = self.get_from_redis(id_user, doc_name)

                if doc:
                    docs.append(doc)
                    self.logger.info(f"Document '{doc_name}' successfully retrieved from Redis storage.")
                    continue

                self.logger.info(f"'{doc_name}' not found in Redis. Trying local filesystem...")

                # 3. Try to retrieve from local filesystem
                doc = self.get_from_local_system(doc_name)

                if doc:
                    docs.append(doc)
                    self.logger.info(f"Document '{doc_name}' successfully retrieved from local system.")
                else:
                    self.logger.warning(f"Document '{doc_name}' could not be found in any source. Skipping.")

        return docs

    def get_from_elastic_search(self, file_name: str) -> dict | None:
        """
        Attempt to retrieve a document by name from ElasticSearch.

        Args:
            file_name (str): Name of the file/document to retrieve.

        Returns:
            dict | None: Document with fields {"name", "text"} if found, otherwise None.
        """
        try:
            db_query = {
                "query": {
                    "bool": {
                        "must": [{"match": {"name": file_name}}]
                    }
                }
            }

            response = self.client.search(index="sperimentazione", body=db_query)

            for hit in response.get("hits", {}).get("hits", []):
                src = hit.get("_source", {})
                if "name" in src and "text" in src:
                    return {"name": src["name"], "text": src["text"]}

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

    def get_from_redis(self, id_user: str, file_name: str) -> dict | None:
        """
        Retrieve a document from Redis cache, scoped by user/session ID.

        Args:
            id_user (str): User/session identifier.
            file_name (str): Document name to retrieve.

        Returns:
            dict | None: Document with {"name", "text"} if found, otherwise None.
        """
        doc = self.storage.get_element(id_user, file_name)
        if doc and "text" in doc:
            return {"name": file_name, "text": doc["text"]}
        return None

    def get_from_local_system(self, file_name: str) -> dict | None:
        """
        Retrieve a document from the local filesystem under `documents/`.

        Args:
            file_name (str): Document name (without extension).

        Returns:
            dict | None: Document with {"name", "text"} if file exists and is valid, otherwise None.
        """
        path_file = os.path.join(self.project_root, "documents", f"{file_name}.json")

        if os.path.exists(path_file):
            try:
                doc = read_file(path_file)
                if "text" in doc:
                    return {"name": file_name, "text": doc["text"]}
                self.logger.warning(f"Local document '{file_name}' is missing 'text' field.")
            except Exception as e:
                self.logger.error(f"Failed to read local document '{file_name}': {e}")
        else:
            self.logger.debug(f"Local document '{file_name}' not found at {path_file}.")

        return None
