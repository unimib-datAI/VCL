from config import Config
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import os

class Generator:
    path = os.path.join("prompts", "generator")
         
    def __init__(self, cfg):
        self.llm = cfg.llm
        self.rag = cfg.rag
        self.read = cfg.read_file
        self.parsers = StrOutputParser()
        
    def generate(self, op: str, docs: list[str], result: str = None) -> str:
        prompt = self.read(os.path.join(self.path, f"0 - IntroductionRAG{str(self.rag)}.txt"))
        
        prompt += "\n\n"
        
        prompt += self.read(os.path.join(self.path, f"1 - {op["comando"]}.txt"))
        
        prompt += "\n\n"
        
        if op["condizione"]:
            prompt += self.read(os.path.join(self.path, f"2 - Conditions.txt"))
            
            for condition in op["condizione"].keys():
                prompt += f"\n- Condizione {condition}: {op['condizione'].get(condition)}"
                
        prompt += "\n\n"
        
        for i in range(len(docs)):
            prompt += f"[Document {i + 1}]\n\n{docs[i]}\n\n"
            
        template = ChatPromptTemplate.from_template(prompt)
            
        chain = template | self.llm | self.parsers
        
        if op["comando"] == "calcola":
            return chain.invoke({"query": op, "response": result})
        else:
            return chain.invoke({"what": op["cosa"]})