from elasticsearch import Elasticsearch

# operations.py
class DQL2Operations:
    @staticmethod
    def generate(dql: dict) -> list[dict]:
        ops = []
        for doc in dql["dove"]:
            ops.append({
                "comando": "Estrai",
                "dove": [doc],
                "cosa": dql["cosa"],
                "condizione": ""
            })
        return ops

class OperationExecutor:
    '''def __init__(self, documents: list[dict]):
        self.docs = {d["type_doc"]: d for d in documents}

    def execute(self, ops: list[dict]) -> list[tuple[str,str]]:
        results = []
        for op in ops:
            doc = self.docs.get(op["dove"][0], "")
            
            if not doc == "":
                results.append((doc["type_doc"], doc["text"]))
            else:
                results.append(("", ""))
        return results'''
        
    def __init__(self, documents: list[dict]):
        self.URL = 'http://10.0.0.108:9201'
        self.client = Elasticsearch(self.URL)
        self.docs = {
            "sentenza di primo grado": "S1 - AN.docx",
            "sentenza di secondo grado": "S2  - AN.docx",
            "memoria giudiziale": "M2  - AN.docx",
            "ricorso giudiziale": "R2 - AN.docx"
        }
        
    def execute(self, ops: list[dict]) -> list[tuple[str,str]]:
        results = []
        for op in ops:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": { "name": self.docs.get(op["dove"][0], "S1 - AN.docx") }
                            }
                        ]
                    }
                }
            }
            
            response = self.client.search(index="sperimentazione", body=query)
            
            # Print results
            for hit in response["hits"]["hits"]:
                print(hit["_source"].keys())
                break
            
            doc = hit["_source"] #self.docs.get(op["dove"][0], "")
            
            if not doc == "":
                results.append((doc["type_doc"], doc["text"]))
            else:
                results.append(("", ""))
        return results