"""Atomic tool for extracting logical or structured elements from context."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def estrai_logico(context: list, query: dict, llm, language) -> str:
    """Extract logically defined elements requested by the DQL query."""
    # Extraction cannot run without source material.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "estrai logico":
        raise ValueError("Error: The command provided does not match 'estrai logico'.")
    
    whats = query.get("what", [])

    if not isinstance(whats, list):
        whats = [whats]

    if len(whats) > 1:
        results = []

        for what in whats:
            sub_query = dict(query)
            sub_query["what"] = [what]

            result = estrai_logico(context, sub_query, llm, language)

            if result:
                results.append(result)

        return "\n\n".join(results)

    try:
        what = whats[0]
    except Exception:
        what = ""

    if not what:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

    # If the whole document is requested, no extraction prompt is needed.
    if what == "intero documento":
        return str(context)

    # Add the target definition so the prompt can extract the right structure.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "what": str(what),
        "description_what": language.get_description_from_what(what.get("name"))
    }

    prompt = language.prompts.get("it", {}).get("EstraiLogico.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    result = llm.invoke(prompt, state)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
