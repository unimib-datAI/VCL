from logic.bot.executor.tools.converters import check_limit_result, format_conditions, format_context, format_limit_condition

def riassumi(context: list, query: dict, llm, language) -> str:
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    if command != "riassumi":
        raise ValueError("Error: The command provided does not match 'riassumi'.")
    
    limit = query.get("how", {}).get("limit", {})
    if not limit:
        limit = {"sign": "<=", "number": 100, "unit": "parole"}
    
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "limit": format_limit_condition(limit)
    }
    prompt = language.prompts.get("Riassumi.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    result = llm.invoke(prompt, state, False)
    return result
    #return check_limit_result(result, context, query, llm, language)