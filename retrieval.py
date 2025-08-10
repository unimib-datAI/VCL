from elasticsearch import Elasticsearch

from config import Config

class Retrieval:
    def __init__(self, cfg: Config):
        self.client = Elasticsearch(cfg.DB_URL)
        
        # TO-DO Update with a dynamic system / annotations
        
        self.docs = {
            "sentenza di primo grado": "S1 - AN.docx",
            "sentenza di secondo grado": "S2  - AN.docx",
            "memoria giudiziale": "M2  - AN.docx",
            "ricorso giudiziale": "R2 - AN.docx"
        }
        
        self.rag = cfg.rag
        
    def execute(self, operation: dict) -> tuple[str,str]:
        if self.rag:
            
            # TO-DO only-chunk retrieval
            
            print("to-do")
            return ("", "")
        else: 
            db_query = {
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
            
            return ("", "")