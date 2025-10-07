import os

from utils.LLM import LLM

llm = LLM.get_instance()

print(llm.invoke_from_file(os.path.join("prompts", "rewriting", "0 - Decomposition.json"),
                     {"query": "estrai il sillogismo dalla sentenza ed unisci in un'unico testo il sillogismo e la sentenza"}))