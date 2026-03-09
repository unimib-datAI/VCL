from logic.bot.executor.tools.converters import check_limit_result, format_conditions, format_context

def estrai_logico(context: list, query: dict, llm, language) -> str:
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    if command != "estrai logico":
        raise ValueError("Error: The command provided does not match 'estrai logico'.")
    
    try:
        what = query.get("what", [])[0]
    except Exception:
        what = ""
    
    if not what:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

    if what == "intero documento":
        return str(context)
    
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "what": str(what),
        "description_what": language.get_description_from_what(what.get("name"))
    }
    
    prompt = language.prompts.get("it", {}).get("EstraiLogico.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    result = llm.invoke(prompt, state)
    return result
    #return check_limit_result(result, context, query, llm, language)