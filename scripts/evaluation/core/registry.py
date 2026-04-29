"""Small registry used to keep evaluation models in a common collection."""

from typing import List
from scripts.evaluation.core.model_base import LLMModel


class ModelRegistry:
    """Store model instances and expose them in registration order."""

    def __init__(self):
        """Create an empty registry."""
        self._models: List[LLMModel] = []

    def register(self, model: LLMModel):
        """Add one model implementation to the registry."""
        self._models.append(model)

    def all(self) -> List[LLMModel]:
        """Return all registered model implementations."""
        return self._models
