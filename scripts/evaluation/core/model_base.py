"""Common interfaces shared by evaluation model wrappers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ModelResponse:
    """Normalized model response shape used by evaluation code."""

    model_name: str
    answer: str
    raw: Any
    metadata: Dict[str, Any]


class LLMModel(ABC):
    """
    Abstract interface for any model adapter used in the evaluation pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the display name used in output files."""
        pass

    @abstractmethod
    def initialize(self, documents: List[Dict[str, Any]]) -> None:
        """
        Optional setup hook, such as building an index or uploading files.
        """
        pass

    @abstractmethod
    def query(self, question: str) -> ModelResponse:
        """Generate an answer for one question."""
        pass
