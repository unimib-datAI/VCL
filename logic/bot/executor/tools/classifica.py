from utils.DQL_language import DQLLanguage
from utils.LLM import LLM

def classifica(context, what, how) -> tuple[str, dict]:
    llm = LLM.get_instance()
    language = DQLLanguage.get_instance()
    
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("classifica"),
        "command": "classifica", 
        "description_command": language.get_description_from_command("classifica"),
        "what": what,
        "description_what": language.get_description_from_what(what)
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)