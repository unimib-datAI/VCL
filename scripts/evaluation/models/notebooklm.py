class NotebookLMModel():
    def __init__(self):
        pass

    @property
    def name(self):
        return "NotebookLM"

    def initialize(self, paths):
        return

    def query(self, question: str) -> str:
        return {
            "content": "",
            "sources": []
        }