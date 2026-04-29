"""Placeholder evaluation adapter for NotebookLM."""

class NotebookLMModel():
    """Minimal NotebookLM adapter that matches the evaluation interface."""

    def __init__(self):
        """No setup is required for the placeholder implementation."""
        pass

    @property
    def name(self):
        """Return the display name used in evaluation outputs."""
        return "NotebookLM"

    def initialize(self, paths):
        """Accept document paths for interface compatibility."""
        return

    def query(self, question: str) -> str:
        """Return an empty response until a real NotebookLM backend is integrated."""
        return {
            "content": "",
            "sources": []
        }
