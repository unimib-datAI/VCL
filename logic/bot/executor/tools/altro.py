def altro(query: str, context: str, llm, language) -> tuple[str, dict]:
    state = {
        "query": query,
        "context": context
    }
    
    prompt = language.prompts.get("GeneratorDefault.json")
    
    return llm.invoke(prompt, state)