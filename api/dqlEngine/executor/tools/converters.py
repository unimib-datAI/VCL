"""Formatting and validation helpers shared by executor tools."""

from utils.file_manager import FileHandler

def format_context(docs: list[dict]) -> str:
    """
    Concatenates multiple retrieved documents into a labeled context block.

    Args:
        docs (list[dict]|str): List of documents with 'type' and 'text', or a single string.

    Returns:
        str: Structured text block for RAG (Retrieval-Augmented Generation).
    """
    if isinstance(docs, str):
        return docs
    
    if not docs:
        return ""
    
    context_lines = []
    for doc in docs:
        # Source attributes let the LLM cite the concrete document, not only its corpus/type.
        source_ref = doc.get("source_ref") or doc.get("name") or doc.get("type", "UNKNOWN")
        source_name = doc.get("source_name") or doc.get("name", source_ref)
        source_type = doc.get("source_type") or doc.get("type", "UNKNOWN")
        context_lines.append(
            f"<DOC source_ref=\"{source_ref}\" source_name=\"{source_name}\" source_type=\"{source_type}\">\n"
            f"\t{doc['text'].lower()}\n"
            f"</DOC>"
        )
    
    context_str = "\n\n".join(context_lines).strip()
    return f"Context:\n{context_str}"

# -----------------------------
# --- Check Limit Condition ---
# -----------------------------
TOLERANCE = 0.20
file_handler = FileHandler()

def check_limit(text: str, constraint: dict) -> bool:
    """
    Validates the generated output against numerical constraints.

    Args:
        text (str): The newly generated response text.
        context (str): The input context (for relative '*' limits).
        constraint (dict): The limit parameters (number, sign, unit).

    Returns:
        bool: True if the text complies with the constraint (including tolerance).
    """
    sign = constraint.get("sign", "")
    number = constraint.get("number")
    unit = constraint.get("unit", "parole")

    if sign == "" or number is None:
        return True

    current_value = file_handler.text_analysis(text, unit)

    is_valid = False
    # if sign == "=":
    #     is_valid = current_value == number
    if sign == "<=" or sign == "<":
        is_valid = current_value <= number
    elif sign == ">=" or sign == ">":
        is_valid = current_value >= number
    elif sign == "~" or sign == "=":
        tolerance = number * TOLERANCE
        is_valid = (number - tolerance) <= current_value <= (number + tolerance)
    else:
        raise ValueError(f"Operatore non supportato: {sign}")

    return is_valid
    
# ----------------------
# --- Input Context  ---
# ----------------------

def format_conditions(how: dict, command: str) -> str:
    """
    Serializes 'how' constraints into natural language instructions for the LLM.

    Args:
        how (dict): Dictionary of extracted constraints (e.g., limit, language).
        command (str): The command being executed (e.g., 'classifica').

    Returns:
        str: A formatted string block to be appended to the prompt.
    """
    if not how:
        return "Non sono presenti condizioni aggiuntive"

    # Block introduction
    conditions = ["L'utente ha posto esplicitamente che la risposta debba soddisfare le seguenti condizioni:"]
    
    for key, value in how.get("others", {}).items():
        if value:
            conditions.append(f"- Condizione \"{key}\": {value}")
            
    if len(how.get("classes", [])) > 0 and command != "classifica":
        conditions.append(f"- Classificazione gli elementi principali del contesto nelle seguenti classi: \"{', '.join(how['classes'])}\".")
    
    if how.get("order", {}) and command != "riorganizza":
        conditions.append(f"- Ordinare gli elementi in ordine \"{how['order'].get('direction', 'crescente')}\" secondo il criterio: {how['order'].get('criteria', 'Alfanumerico')}.")
    
    if how.get("limit", {}) and command not in ["riassumi", "riformula"]:
        limit_text = format_limit_condition(how['limit'])
        if limit_text:
            conditions.append(f"- {limit_text}")

    return "\n".join(conditions) if len(conditions) > 1 else "Non sono presenti condizioni aggiuntive"

def format_limit_condition(limit: dict) -> str:
    """Render a numerical limit as an instruction for the LLM."""
    sign = limit.get('sign', '~')
    unit = limit.get('unit', 'parole')
    number = limit.get('number', 50)
        
    if sign == "<=" or sign == "<":
        sign = "meno di "
    elif sign == ">=" or sign == ">":
        sign = "più di"
    elif sign == "~" or sign == "=":
        sign = "circa"
    else:
        return None
    
    return f"È obbligatorio che la risposta abbia {sign} {number} {unit}."

# --------------------------
# --- Check Limit Result ---
# --------------------------

def check_limit_result(result: str, context: str, query, llm, dql) -> str:
    """
    Retry answer generation when the response violates the requested length limit.
    """
    if query.get("how", {}).get("limit", None) is None:
        return result
    
    limit_cfg = query["how"]["limit"]
    
    attempt = 0
    
    while attempt < 3 and limit_cfg:
        is_valid = check_limit(result, limit_cfg)
        
        if is_valid:
            break
            
        attempt += 1
        
        current_val = file_handler.text_analysis(result, limit_cfg['unit'])
        target_val = limit_cfg['number']
        
        diff = current_val - target_val
        if diff > 0:
            feedback = f"ERRORE: La risposta è troppo LUNGA. Hai scritto {current_val} {limit_cfg['unit']}, ma il limite è {target_val}. Devi TAGLIARE circa {abs(diff)} {limit_cfg['unit']}."
        else:
            feedback = f"ERRORE: La risposta è troppo CORTA. Hai scritto {current_val} {limit_cfg['unit']}, ma il limite è {target_val}. Devi ESPANDERE di circa {abs(diff)} {limit_cfg['unit']}."

        new_context = "\t" + "\n\t".join(format_context(context).split("\n")).strip()
        new_context = (
            f"{feedback}\n\n"
            f"[TESTO DA CORREGGERE]\n{result}\n\n"
            f"[CONTESTO ORIGINALE PER RIFERIMENTO]\n{new_context}"
        )
        
        # Reuse the rephrasing prompt to adjust only the response length.
        result = riformula(new_context, query, llm, dql)
        
    return result

def riformula(context: list, query: dict, llm, language) -> str:
    """Ask the LLM to rewrite an answer so it respects the extracted limits."""
    if not context:
        return "Non è stato possibile rispondere alla tua richiesta perché non ho trovato i documenti richiesti."
    
    command = query.get("command")
    
    limit = query.get("how", {}).get("limit", {})
    if not limit:
        return context
    
    state = {
        "how": format_conditions(query.get("how", {}), command),
        "context": format_context(context),
        "limit": format_limit_condition(limit)
    }
    
    prompt = language.prompts.get("it", {}).get("Riformula.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
    
    return llm.invoke(prompt, state)
