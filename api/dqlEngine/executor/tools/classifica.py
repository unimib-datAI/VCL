"""Atomic tool that classifies retrieved content into user-provided classes."""

from api.dqlEngine.executor.tools.converters import check_limit_result, format_conditions, format_context

def classifica(context: list, query: dict, llm, language) -> str:
    """Classify the context according to the classes extracted in the 'how' block."""
    # Classification requires retrieved text to assign into classes.
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."

    # Validate that the dispatcher selected the matching atomic tool.
    command = query.get("command")
    if command != "classifica":
        raise ValueError("Error: The command provided does not match 'classifica'.")

    # Classes are mandatory because the prompt needs explicit output buckets.
    classes = query.get("how", {}).get("classes", [])
    if not classes or len(classes) == 0:
        return "Non sono in grado di elaborare la richiesta in quanto non è stata fornita una lista di classi."

    # Prepare prompt variables with formatted context and class labels.
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "classes": str(classes)
    }

    prompt = language.prompts.get("it", {}).get("Classifica.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")

    # Invoke the model and return the classification result.
    result = llm.invoke(prompt, state)
    return result
    # Limit enforcement is currently disabled for this tool.
    # return check_limit_result(result, context, query, llm, language)
