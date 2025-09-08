from utils.config import Config
from graph import Graph

class Rewriting:
    def __init__(self, cfg: Config):
        self.graph = Graph(cfg).graph
    
    def rewrite(self, query: str, id: str) -> dict:
        # Configuration containing the conversation ID
        config = {"configurable": {"thread_id": id}}

        # Asynchronously invoke the graph processing function with the initial state and configuration
        response = self.graph.invoke(self.initial_state(query, id), config=config)

        return response["response"]
        
    @staticmethod
    def initial_state(query: str, id: str) -> dict:
        return {
            "query": query,      # Original user query
            "thread_id": id,
            "command": "",
            "description_command": "",
            "documents": [],
            "id_result": "",
            "unit": "",
            "what_name": "",
            "what_type": "",
            "what_description": "",
            "how_section": "",
            "how_data": "",
            "how_response": "",
            "iteration": 0,
            "feedback": "",
            "response": {}
        }
