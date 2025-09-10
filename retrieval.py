import os
import json
from elasticsearch import Elasticsearch

from utils.config import Config
from utils.file_manager import read_file


class Retrieval:
    def __init__(self, cfg: Config):
        self.client = Elasticsearch(cfg.DB_URL)
        self.storage = cfg.storage
        self.rag = False  # self.rag = cfg.rag
        self.logger = cfg.logger

    def execute(self, operation: dict, id_user: str) -> list[dict]:
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
            # TO-DO only-chunk retrieval
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
                    path_file = os.path.join("documents", f"{d}.json")

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
