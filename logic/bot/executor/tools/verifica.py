def verifica(context, what, how, llm, language) -> tuple[str, dict]:
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("verifica"),
        "command": "verifica", 
        "description_command": language.get_description_from_command("verifica"),
        "what": what[0],
        "description_what": language.get_description_from_what(what[0])
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)