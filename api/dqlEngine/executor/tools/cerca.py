"""Atomic search tools for concepts, phrases, and document-wide lookup."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context


def cerca(context: list, query: dict, llm, language) -> str:
    """Search the retrieved context for the requested target."""
    # Retrieval must provide at least one document before search can run.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "cerca":
        raise ValueError("Error: The command provided does not match 'cerca'.")

    # Support both single and multi-what flows.
    whats = query.get("what", [])
    if not isinstance(whats, list):
        whats = [whats]

    if len(whats) > 1:
        results = []

        for what in whats:
            sub_query = dict(query)
            sub_query["what"] = [what]

            result = cerca(context, sub_query, llm, language)
            if result:
                results.append(result)

        return "\n\n".join(results)

    # Single target selection.
    try:
        what = whats[0]
    except (IndexError, TypeError):
        what = {}

    if not isinstance(what, dict):
        if isinstance(what, str):
            what = {"name": what}
        else:
            what = {}

    what_name = what.get("name", None)

    if not what_name:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

    # Full-document search is already satisfied by returning the retrieved context.
    if what_name == "intero documento":
        return str(context)

    # Route each target type to the prompt that best matches its semantics.
    state = {}
    if what_name == "frase":
        return cerca_frase(what, context, language, llm)
    elif what_name == "concetto":
        prompt = language.prompts.get("it", {}).get("CercaConcetto.json")
        concept = what.get("element", None)

        if not concept:
            return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

        state = {
            "how": format_conditions(query.get("how", {}), command),
            "context": format_context(context),
            "what": concept,
        }
    else:
        prompt = language.prompts.get("it", {}).get("Cerca.json")

        state = {
            "how": format_conditions(query.get("how", {}), command),
            "context": format_context(context),
            "what": what_name,
            "description_what": language.get_description_from_what(what_name),
        }

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Execute the selected prompt and return the search result.
    result = llm.invoke(prompt, state)
    return result


def cerca_frase(what, context, language, llm):
    """Find a phrase and ask the LLM for the surrounding sentence."""
    what_name = what.get("element")
    if not what_name:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho capito cosa cercare."

    f_context = format_context(context)

    # If the exact phrase is not present, ask the LLM to locate the closest match.
    if what_name not in f_context:
        state = {
            "context": f_context,
            "what": what.get("element"),
        }

        prompt = language.prompts.get("it", {}).get("CercaFrase1.json")

        if not prompt:
            raise ValueError("Error: Could not determine how to process this request.")

        result = llm.invoke(prompt, state)
    else:
        result = what_name

    if result not in f_context:
        return f"L'elemento \"{what_name}\" non è presente nel testo."

    # Restrict the second prompt to a local window around the phrase.
    idx_start = f_context.index(result)
    idx_end = idx_start + len(result)

    window_start = max(0, idx_start - 2000)
    window_end = min(len(f_context), idx_end + 100)

    f_context_window = f_context[window_start:window_end]

    # Ask a second prompt to extract the complete surrounding sentence.
    prompt = language.prompts.get("it", {}).get("CercaFrase2.json")
    state = {
        "context": f_context_window,
        "what": what.get("element"),
    }

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    result = llm.invoke(prompt, state)

    if "ERRORE" in result:
        return f"L'elemento \"{what_name}\" è presente nel testo, ma non ha una frase identificabile."

    return result
