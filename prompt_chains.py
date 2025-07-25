# prompt_chains.py
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import Runnable
import os

class PromptChains:
    def __init__(self, model_name: str = "gemini-2.0-flash", provider: str = "google_genai"):
        self.llm = init_chat_model(model_name, model_provider=provider)
        self.parsers = StrOutputParser()

        # Initialize all chains
        self.chain_1 = self._make_chain("CorrectionQuery")
        self.chain_2 = self._make_chain("IntentClassification")
        self.chain_3a = self._make_chain("DocumentExtraction")
        self.chain_3b = self._make_chain("WhatExtraction")
        self.chain_3c = self._make_chain("ConditionsExtraction")
        self.chain_4 = self._make_chain("EntityDisambiguation")
        self.chain_5 = self._make_chain("PhraseDisambiguation")
        self.evaluator = self._make_chain("EvaluationResult")
        self.reflection = self._make_chain("CorrectionResult")
        self.result_1 = self._make_chain("Result")
        self.result_2 = self._make_chain("Result2")

    def _make_chain(self, name: str) -> Runnable:
        """
        Create a runnable chain from a prompt file and attach LLM and parser.
        """
        path = os.path.join("prompts", f"{name}.txt")
        template = ChatPromptTemplate.from_template(open(path, "r").read())
        return template | self.llm | self.parsers
