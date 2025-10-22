import os

from spellchecker import SpellChecker

from bot.utils.config import Config

class SpellingChecker:
    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.project_root = cfg.project_root
        self.spell = SpellChecker(language="it")
       
    def correct_text(self, text: str) -> str:
        words = text.lower().split()
        corrected_words = [self.spell.correction(word) for word in words]
        return " ".join(filter(None, corrected_words))
    
    def correct_text_llm(self, text: str) -> str:
        return self.llm.invoke_from_file(
            os.path.join(self.project_root, "documents", "prompts", "rewriting", f"1 - CorrectionQuery.json"),
            {"query": text}
        )