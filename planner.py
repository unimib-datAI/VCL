from utils.config import Config

class Planner:
    def __init__(self, cfg: Config):
        # TO-DO Update with a dynamic system / annotations
        self.docs = {
            "sentenza di primo grado": "S1 - AN",
            "sentenza di secondo grado": "S2  - AN",
            "memoria giudiziale": "M2  - AN",
            "ricorso giudiziale": "R2 - AN"
        }
        
    def decompose(self, query: dict) -> list[dict]:
        ops = []
        
        if query["command"] == "cerca" or query["command"] == "estrai":
            if len(query["documents"]) > 1:
                ops = self.getMiddleOperations(query, "unisci")
            else:
                query["command"] = self.getSubCommand(query)
                query["documents"] = [self.docs.get(query["documents"][0], query["documents"][0])]
                ops.append(query)
        elif query["command"] == "esplora":
            query["command"] = "cerca"
            ops = self.decompose(query)
        else:
            ops = self.getMiddleOperations(query, query["command"])                
        
        print(ops)
          
        return ops
    
    def getMiddleOperations(self, query, new_command):
        ops = []
        sub_command = self.getSubCommand(query)
                
        for i in range(len(query["documents"])): 
            ops.append({
                "command": sub_command,
                "documents": [self.docs.get(query["documents"][i], query["documents"][i])],
                "id": f"{query["id"]}_{i}",
                "what": query["what"],
                "how": {}
            })
            
            id_docs = [d["id"] for d in ops]
            
            print(id_docs)
            
            final_op = {
                "command": new_command,
                "documents": id_docs,
                "what": query["what"],
                "how": query["how"],
                "id": f"{query["id"]}"
            }
            
            if new_command == "calcola":
                final_op.update({"unit": query["unit"]})
                
            ops.append(final_op)
        
        return ops
        
    def getSubCommand(self, query):
        if query["what"]["name"] == "entità":
            return "cerca"
        else:
            return "estrai"