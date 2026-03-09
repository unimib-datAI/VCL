from logic.bot.executor.tools.converters import check_limit_result, format_conditions, format_context

def riorganizza(context: list, query: dict, llm, language) -> str:
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    if command != "riorganizza":
        raise ValueError("Error: The command provided does not match 'riorganizza'.")
    
    order = query.get("how", {}).get("order", {})
    if not order or not isinstance(order, dict):
        order = {}
        
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "criteria": order.get("criteria", "Alfanumerico"),
        "direction": order.get("direction", "Crescente")
    }
    
    prompt = language.prompts.get("it", {}).get("Riorganizza.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    result = llm.invoke(prompt, state)
    return result
    #return check_limit_result(result, context, query, llm, language)