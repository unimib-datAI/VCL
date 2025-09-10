import json
from utils.config import Config
from graph import Graph


class Rewriting:
    def __init__(self, cfg: Config):
        self.graph = Graph(cfg).graph
        self.logger = cfg.logger

    def rewrite(self, query: str, id_user: str) -> dict:
        self.logger.info(
            json.dumps(
                {
                    "step": "Rewriting.rewrite",
                    "action": "start",
                    "query": query,
                    "user": id_user,
                }
            )
        )

        config = {"configurable": {"thread_id": id_user}}
        response = self.graph.invoke(self.initial_state(query, id_user), config=config)

        self.logger.info(
            json.dumps(
                {
                    "step": "Rewriting.rewrite",
                    "action": "end",
                    "response": response["response"],
                }
            )
        )
        return response["response"]

    @staticmethod
    def initial_state(query: str, id_user: str) -> dict:
        return {
            "query": query,
            "thread_id": id_user,
            "command": "",
            "description_command": "",
            "documents": [],
            "id_user_result": "",
            "unit": "",
            "what_name": "",
            "what_type": "",
            "what_description": "",
            "how_section": "",
            "how_data": "",
            "how_response": "",
            "iteration": 1,
            "feedback": "",
            "response": {},
        }
