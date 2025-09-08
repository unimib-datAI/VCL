from elasticsearch import Elasticsearch

from utils.config import Config
from utils.file_manager import read_file

import os

class Retrieval:
    def __init__(self, cfg: Config):
        self.client = Elasticsearch(cfg.DB_URL)
        
        self.storage = cfg.storage
        #self.rag = cfg.rag
        self.rag = False
        
    def execute(self, operation: dict, id: str) -> list[dict]:
        if self.rag:
            
            # TO-DO only-chunk retrieval
            
            print("to-do")
            return [{
                "name": "",
                "text": ""
            }]
        else: 
            '''db_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": { "name": self.docs.get(operation["dove"][0], self.docs.values[0]) }
                            }
                        ]
                    }
                }
            }
            
            response = self.client.search(index="sperimentazione", body=db_query)
            
            for hit in response["hits"]["hits"]:
                if "name" in hit["_source"].keys() and "text" in hit["_source"].keys():
                    return (hit["_source"]["name"], hit["_source"]["text"])
            
            return ("", "")'''
            
            docs = []
            for d in operation["documents"]:
                doc = self.storage.get_element(id, d)
                
                if not (doc is None):
                    docs.append({
                        "name": d,
                        "text": doc["text"]
                    })
                else:
                    path_file = os.path.join("documents", f"{d}.json")
                
                    if os.path.exists(path_file):
                        file = read_file(path_file)
                        
                        docs.append({
                            "name": d,
                            "text": file["text"]
                        })
                    else:
                        print("File not Found")
            
            return docs