def altro(query: str, context: str, llm, language) -> tuple[str, dict]:
    state = {
        "query": query,
        "context": context
    }
    
    prompt = language.prompts.get("GeneratorDefault.json")
    
    if not prompt:
        raise ValueError("Error: Could not determine how to process this request.")
    
    return llm.invoke(prompt, state)