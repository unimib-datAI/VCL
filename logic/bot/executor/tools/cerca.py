from logic.bot.executor.tools.converters import check_limit_result, format_conditions, format_context

def cerca(context: list, query: dict, llm, language) -> str:
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    if command != "cerca":
        raise ValueError("Error: The command provided does not match 'cerca'.")
    
    try:
        what = query.get("what", [])[0]
    except Exception:
        what = {}
    
    what_name = what.get("name", None)
    
    if not what_name:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

    if what_name == "intero documento":
        return str(context)
    
    state = {}
    if what_name == "frase":
        prompt = language.prompts.get("CercaFrase.json")
        what_name = what.get("element")
        
        state = {
            "context": format_context(context),
            "what": what.get("element")
        }
    elif what_name == "concetto":
        prompt = language.prompts.get("CercaConcetto.json")
        what_name = what.get("element")
        
        state = {
            "how": format_conditions(query.get("how", {}), command),
            "context": format_context(context),
            "what": what_name
        }
    else:
        prompt = language.prompts.get("Cerca.json")
        
        state = {
            "how": format_conditions(query.get("how", {}), command),
            "context": format_context(context),
            "what": what_name,
            "description_what": language.get_description_from_what(what_name)
        }
    
    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
    
    result = llm.invoke(prompt, state)
    return result
    #return check_limit_result(result, context, query, llm, language)