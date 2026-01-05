def riformula(context, what, how, llm, language) -> tuple[str, dict]:
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("riformula"),
        "command": "riformula", 
        "description_command": language.get_description_from_command("riformula"),
        "what": "intero documento",
        "description_what": "considera l'intero contesto"
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)