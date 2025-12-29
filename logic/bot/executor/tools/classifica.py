def classifica(context, what, how, llm, language) -> tuple[str, dict]:
    state = {
        "how": how,
        "context": context,
        "guidelines": language.get_guidelines_from_command("classifica"),
        "command": "classifica", 
        "description_command": language.get_description_from_command("classifica"),
        "what": what[0],
        "description_what": language.get_description_from_what(what[0])
    }
    prompt = language.prompts.get("Generator.json")

    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
        
    return llm.invoke(prompt, state)