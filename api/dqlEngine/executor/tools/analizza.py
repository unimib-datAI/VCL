"""Atomic tool for analytical answers over retrieved context."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def analizza(context: list, query: dict, llm, language) -> str:
    """Analyze the provided documents using the DQL analysis prompt."""
    # Stop early when retrieval did not return any usable material.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "analizza":
        raise ValueError("Error: The command provided does not match 'analizza'.")

    # Build the compact state passed to the prompt template.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context)
    }

    # Resolve the prompt lazily from the active DQL language configuration.
    prompt = language.prompts.get("it", {}).get("Analizza.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Invoke the model and return the raw analytical answer.
    result = llm.invoke(prompt, state, False)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
