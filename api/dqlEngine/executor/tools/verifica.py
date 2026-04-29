"""Atomic verification tool for checking statements against context."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def verifica(context: list, query: dict, llm, language) -> str:
    """Verify the requested claim or condition using the retrieved documents."""
    # Verification requires evidence from the selected sources.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "verifica":
        raise ValueError("Error: The command provided does not match 'verifica'.")

    # The prompt receives all evidence plus any extracted conditions.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context)
    }

    prompt = language.prompts.get("it", {}).get("Verifica.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    result = llm.invoke(prompt, state, False)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
