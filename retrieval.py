"""
Retrieval module for fetching documents required by operations.

Responsibilities:
- Retrieve documents either from:
  * Storage (Redis wrapper).
  * Local filesystem (fallback).
  * (Future) ElasticSearch or chunk-based retrieval (RAG mode).
- Ensure structured logging of each retrieval attempt and outcome.

Dependencies:
- utils.config.Config: Provides shared logger, storage instance, DB URL.
- utils.file_manager.read_file: Utility to read JSON/text documents.
- elasticsearch.Elasticsearch: Potential search backend (currently unused).
"""

import os
import json
from elasticsearch import Elasticsearch

from utils.config import Config
from utils.file_manager import read_file


class Retrieval:
    """
    Document retriever that fetches input data for operations.

    Attributes:
        client (Elasticsearch): Elasticsearch client instance (currently unused).
        storage (Storage): Reference to shared Redis storage instance.
        rag (bool): Flag for enabling Retrieval-Augmented Generation mode (TO-DO).
        logger: Logger instance for structured JSON logs.
    """

    def __init__(self, cfg: Config):
        """
        Initialize Retrieval with config.

        Args:
            cfg (Config): Shared application configuration.
        """
        self.client = Elasticsearch(cfg.DB_URL)  # Future ElasticSearch usage
        self.storage = cfg.storage
        self.rag = False  # TODO: switch to cfg.rag once RAG is implemented
        self.logger = cfg.logger
        self.project_root = cfg.project_root

    def execute(self, operation: dict, id_user: str) -> list[dict]:
        """
        Execute document retrieval for a given operation.

        Priority order:
        1. (Future) RAG mode retrieval → not implemented, placeholder only.
        2. Redis storage (session-specific documents).
        3. Local filesystem fallback under `documents/`.

        Args:
            operation (dict): Operation containing `documents` list.
            id_user (str): User/session identifier to scope storage lookup.

        Returns:
            list[dict]: List of retrieved documents with fields:
                - "name" (str): Document identifier.
                - "text" (str): Full text content.
        """
        self.logger.info(
            json.dumps(
                {
                    "step": "Retrieval.execute",
                    "action": "start",
                    "operation": operation,
                    "user": id_user,
                }
            )
        )

        docs = []

        if self.rag:
            # Placeholder for Retrieval-Augmented Generation
            self.logger.info(
                json.dumps(
                    {
                        "step": "Retrieval.execute",
                        "action": "rag_mode",
                        "message": "TO-DO only-chunk retrieval",
                    }
                )
            )
            docs = [{"name": "", "text": ""}]
        else:
            for d in operation["documents"]:
                # 1. Try Redis storage first
                doc = self.storage.get_element(id_user, d)

                if doc is not None:
                    docs.append({"name": d, "text": doc["text"]})
                    self.logger.info(
                        json.dumps(
                            {
                                "step": "Retrieval.execute",
                                "action": "from_storage",
                                "document": d,
                                "status": "found",
                            }
                        )
                    )
                else:
                    # 2. Fallback: filesystem documents/<doc>.json
                    path_file = os.path.join(self.project_root, "documents", f"{d}.json")

                    if os.path.exists(path_file):
                        file = read_file(path_file)
                        docs.append({"name": d, "text": file["text"]})
                        self.logger.info(
                            json.dumps(
                                {
                                    "step": "Retrieval.execute",
                                    "action": "from_filesystem",
                                    "document": d,
                                    "path": path_file,
                                    "status": "found",
                                }
                            )
                        )
                    else:
                        # Log missing document
                        self.logger.warning(
                            json.dumps(
                                {
                                    "step": "Retrieval.execute",
                                    "action": "missing",
                                    "document": d,
                                    "path": path_file,
                                    "status": "not_found",
                                }
                            )
                        )

        self.logger.info(
            json.dumps(
                {"step": "Retrieval.execute", "action": "end", "retrieved_docs": docs}
            )
        )
        return docs
