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
        '''prompt = language.prompts.get("CercaFrase.json")
        what_name = what.get("element")
        
        state = {
            "context": format_context(context),
            "what": what.get("element")
        }'''
        return cerca_frase(what, context, language, llm)
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

def cerca_frase(what, context, language, llm):
    what_name = what.get("element")
    
    f_context = format_context(context)
    
    if what_name not in f_context: 
        state = {
            "context": f_context,
            "what": what.get("element")
        }
        
        prompt = language.prompts.get("CercaFrase1.json")
        
        if not prompt:
            raise ValueError("Error: Could not determine how to process this request.")
        
        result = llm.invoke(prompt, state)
    else:
        result = what_name 
        
    print(result)
    if result not in f_context:
        return f"L'elemento \"{what_name}\" non è stato trovato nel testo"
    
    idx_start = f_context.index(result)
    idx_end = idx_start + len(result)

    window_start = max(0, idx_start - 2000)
    window_end = min(len(f_context), idx_end + 100)

    f_context_window = f_context[window_start:window_end]
    
    prompt = language.prompts.get("CercaFrase2.json")
    state = {
        "context": f_context_window,
        "what": what.get("element")
    }
    
    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
    
    result = llm.invoke(prompt, state)
    return result