from utils.DQL_language import DQLLanguage
from utils.LLM import LLM

def cerca(context, what, how, llm, language) -> tuple[str, dict]:
    if what == "intero documento":
        return context
    
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("cerca"),
        "command": "cerca", 
        "description_command": language.get_description_from_command("cerca"),
        "what": what[0],
        "description_what": language.get_description_from_what(what[0])
    }
    prompt = language.prompts.get("Generator.json")
    
    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)