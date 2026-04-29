"""Atomic tool for comparing multiple retrieved documents or results."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def confronta(context: list, query: dict, llm, language) -> str:
    """Compare the provided context items with the dedicated DQL prompt."""
    # Comparison requires at least one retrieved item.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "confronta":
        raise ValueError("Error: The command provided does not match 'confronta'.")

    # Build the state with optional conditions and all items to compare.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context)
    }

    prompt = language.prompts.get("it", {}).get("Confronta.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Disable extractor parsing because this prompt is expected to return free text.
    result = llm.invoke(prompt, state, False, False)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
