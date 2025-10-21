import json

from bot.utils.config import Config

class Planner:
    def __init__(self, cfg: Config):
        self.logger = cfg.get_logger("Planner")

    def decompose(self, query: dict) -> list[dict]:
        ops = []

        if query["command"] in ["cerca", "estrai"]:
            if len(query["documents"]) > 1:
                ops = self.get_middle_operations(query, "unisci")
            else:
                query["command"] = self.get_sub_command(query)
                query["documents"] = [
                    self.docs.get(query["documents"][0], query["documents"][0])
                ]
                ops.append(query)
        elif query["command"] == "esplora":
            query["command"] = "cerca"
            ops = self.decompose(query)
        else:
            ops = self.get_middle_operations(query, query["command"])

        return ops

    def get_middle_operations(self, query: dict, new_command: str) -> list[dict]:
        ops = []
        sub_command = self.get_sub_command(query)

        # One sub-operation per document
        for i in range(len(query["documents"])):
            ops.append(
                {
                    "command": sub_command,
                    "documents": [
                        self.docs.get(query["documents"][i], query["documents"][i])
                    ],
                    "id": f"{query['id']}_{i}",
                    "what": query["what"],
                    "how": {},
                }
            )

        # IDs of intermediate results
        id_docs = [d["id"] for d in ops]

        # Final operation combining results
        final_op = {
            "command": new_command,
            "documents": id_docs,
            "what": query["what"],
            "how": query["how"],
            "id": f"{query['id']}",
        }

        if new_command == "calcola":
            final_op.update({"unit": query["unit"]})

        ops.append(final_op)

        return ops

    def get_sub_command(self, query: dict) -> str:
        if query["what"]["name"] == "entità":
            command = "cerca"
        else:
            command = "estrai"

        self.logger.info(
            json.dumps(
                {
                    "step": "Planner.get_sub_command",
                    "decision": command,
                    "based_on": query["what"],
                }
            )
        )
        return command
