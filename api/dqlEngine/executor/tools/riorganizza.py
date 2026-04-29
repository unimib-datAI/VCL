"""Atomic tool that reorganizes retrieved content by a selected criterion."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def riorganizza(context: list, query: dict, llm, language) -> str:
    """Reorder or restructure the context according to extracted order settings."""
    # Reorganization needs retrieved content to sort or reshape.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "riorganizza":
        raise ValueError("Error: The command provided does not match 'riorganizza'.")

    # Use default ordering values when extraction produced no valid order block.
    order = query.get("how", {}).get("order", {})
    if not order or not isinstance(order, dict):
        order = {}

    # Pass both raw context and ordering metadata to the prompt.
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
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
