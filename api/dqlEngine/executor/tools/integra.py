"""Atomic tool that merges multiple partial answers into one response."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def integra(context: list, query: dict, llm, language) -> str:
    """Integrate one or more retrieved results into a final coherent answer."""
    # Integration needs at least one partial result to combine.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # A single unconstrained result does not need another LLM pass.
    if len(context) == 1 and not query.get("how", {}):
        return context[0]

    command = query.get("command")

    # Format all partial results as one integration context.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context)
    }

    prompt = language.prompts.get("it", {}).get("Integra.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Disable extractor parsing because integration returns free-form text.
    result = llm.invoke(prompt, state, False, False)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
