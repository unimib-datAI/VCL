from utils.DQL_language import DQLLanguage
from utils.LLM import LLM

def estrai_semantico(context, what, how, llm, language) -> tuple[str, dict]:
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("estrai semantico"),
        "command": "estrai semantico", 
        "description_command": language.get_description_from_command("estrai semantico"),
        "what": what[0],
        "description_what": language.get_description_from_what(what[0])
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)