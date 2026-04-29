"""Atomic summarization tool with optional length constraints."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context, format_limit_condition

def riassumi(context: list, query: dict, llm, language) -> str:
    """Summarize retrieved context using explicit or default length limits."""
    # Summarization needs retrieved material to condense.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "riassumi":
        raise ValueError("Error: The command provided does not match 'riassumi'.")

    # Apply a conservative default length when the user did not specify one.
    limit = query.get("how", {}).get("limit", {})
    if not limit:
        limit = {"sign": "<=", "number": 100, "unit": "parole"}

    # Include both general conditions and the explicit summary limit.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "limit": format_limit_condition(limit)
    }
    prompt = language.prompts.get("it", {}).get("Riassumi.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Disable extractor parsing because summaries are free-form text.
    result = llm.invoke(prompt, state, False, False)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
