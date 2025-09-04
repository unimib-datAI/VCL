from utils.config import Config
from utils.file_manager import read_file
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import os
import time

class Generator:
    path = os.path.join("prompts", "generator")
         
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.rag = cfg.rag
        self.seconds = cfg.seconds
        self.parsers = StrOutputParser()
        
    def generate(self, op: str, docs: list[dict], query: str) -> str:
        if (op["command"] == "estrai" or op["command"] == "cerca") and op["what"]["name"] == "intero documento":
            return "\n\n".join([d["text"] for d in docs]).strip()
                
        template = read_file(os.path.join(self.path, f"{op["command"]}.json"))
        
        template["system"] = "\n".join(template["system"])
        template["human"] = "\n".join(template["human"])
        
        conditions = ""
        if not (op["how"] == {}):
            conditions = "\nInoltre la risposta deve rispettare le seguenti condizioni:"
            
            for condition in op["how"].keys():
                if op["how"][condition]:
                    conditions += f"\n- Condizione {condition}: {op['how'].get(condition)}"
                    
        if not (conditions == "" or conditions == "\nInoltre la risposta deve rispettare le seguenti condizioni:"):
            template["system"] += f"\n{conditions}"
            
        context = ""
        for i in range(len(docs)):
            context += f"[Document {i + 1}]\n\n{docs[i]}\n\n"
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", template["system"]),
            ("human", template["human"])
        ])
            
        chain = prompt | self.llm | self.parsers
        
        result = chain.invoke({"query": query, "context": context})
            
        time.sleep(self.seconds)
        
        return result