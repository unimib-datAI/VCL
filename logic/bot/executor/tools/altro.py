from utils.DQL_language import DQLLanguage
from utils.LLM import LLM

def altro(query: str, context: str) -> tuple[str, dict]:
    llm = LLM.get_instance()
    language = DQLLanguage.get_instance()
    
    state = {
        "query": query,
        "context": context
    }
    
    prompt = language.prompts.get("GeneratorDefault.json")
    
    return llm.invoke(prompt, state)