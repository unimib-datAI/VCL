from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ModelResponse:
    model_name: str
    answer: str
    raw: Any
    metadata: Dict[str, Any]


class LLMModel(ABC):
    """
    Interfaccia astratta per QUALSIASI modello (LLM, RAG, tool, ecc.)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def initialize(self, documents: List[Dict[str, Any]]) -> None:
        """
        Hook opzionale (es. build index RAG, upload file, ecc.)
        """
        pass

    @abstractmethod
    def query(self, question: str) -> ModelResponse:
        pass
