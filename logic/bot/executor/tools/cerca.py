from utils.DQL_language import DQLLanguage
from utils.LLM import LLM

def cerca(context, what, how) -> tuple[str, dict]:
    llm = LLM.get_instance()
    language = DQLLanguage.get_instance()
    
    if what == "intero documento":
        return context
    
    state = {
        "feedback": "",
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("cerca"),
        "command": "cerca", 
        "description_command": language.get_description_from_command("cerca"),
        "what": what,
        "description_what": language.get_description_from_what(what)
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)