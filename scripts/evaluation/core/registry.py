from typing import List
from scripts.evaluation.core.model_base import LLMModel


class ModelRegistry:
    def __init__(self):
        self._models: List[LLMModel] = []

    def register(self, model: LLMModel):
        self._models.append(model)

    def all(self) -> List[LLMModel]:
        return self._models
