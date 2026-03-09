from logic.bot.executor.tools.converters import check_limit_result, format_conditions, format_context

def classifica(context: list, query: dict, llm, language) -> str:
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    if command != "classifica":
        raise ValueError("Error: The command provided does not match 'classifica'.")
    
    classes = query.get("how", {}).get("classes", [])
    if not classes or len(classes) == 0:
        return "Non sono in grado di elaborare la richiesta in quanto non è stata fornita una lista di classi."
    
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "classes": str(classes)
    }
    
    prompt = language.prompts.get("it", {}).get("Classifica.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    result = llm.invoke(prompt, state)
    return result
    #return check_limit_result(result, context, query, llm, language)