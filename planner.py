"""
Planner module for decomposing high-level queries into executable operations.

Responsibilities:
- Decide the appropriate sequence of sub-operations (ops) for a given query.
- Handle special cases like multiple documents or "explore" operations.
- Map human-friendly document names (e.g., "sentenza di primo grado") to IDs.
- Insert intermediate operations when multiple steps are required (e.g., merge).

Dependencies:
- utils.config.Config: Provides shared logger.
"""

import json
from utils.config import Config


class Planner:
    """
    Planner class responsible for breaking down user queries into structured
    operations that can later be executed by the system.

    Attributes:
        docs (dict): Mapping between natural-language document names and document IDs.
        logger: Logger instance for structured execution logging.
    """

    def __init__(self, cfg: Config):
        """
        Initialize Planner with document mappings and logger.

        Args:
            cfg (Config): Shared configuration object.
        """
        self.docs = {
            "sentenza di primo grado": "S1 - AN",
            "sentenza di secondo grado": "S2 - AN",
            "memoria giudiziale": "M2 - AN",
            "ricorso giudiziale": "R2 - AN",
        }
        self.logger = cfg.logger

    def decompose(self, query: dict) -> list[dict]:
        """
        Decompose a query into one or more operations.

        Logic:
        - If `command` is "cerca" or "estrai":
          * If multiple documents → create sub-operations + merge step.
          * If single document → normalize command and document name.
        - If `command` is "esplora" → rewrite into "cerca" and decompose again.
        - Else → delegate to get_middle_operations with the given command.

        Args:
            query (dict): Input query containing command, documents, what, how, id, etc.

        Returns:
            list[dict]: List of operations, including possible intermediate steps.
        """
        self.logger.info(
            json.dumps({"step": "Planner.decompose", "action": "start", "input": query})
        )
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
            ops = self.decompose(query)  # Recursive rewrite
        else:
            ops = self.get_middle_operations(query, query["command"])

        self.logger.info(
            json.dumps({"step": "Planner.decompose", "action": "end", "output": ops})
        )
        return ops

    def get_middle_operations(self, query: dict, new_command: str) -> list[dict]:
        """
        Generate intermediate operations when a query spans multiple documents.

        Steps:
        - Break down query into sub-operations (one per document).
        - Collect IDs of sub-operations.
        - Add a final "merge" or other aggregate operation.

        Args:
            query (dict): Input query definition.
            new_command (str): The final aggregation command (e.g., "unisci", "calcola").

        Returns:
            list[dict]: Sequence of sub-operations + final aggregation step.
        """
        self.logger.info(
            json.dumps(
                {
                    "step": "Planner.get_middle_operations",
                    "action": "start",
                    "input": query,
                    "new_command": new_command,
                }
            )
        )
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

        self.logger.info(
            json.dumps(
                {
                    "step": "Planner.get_middle_operations",
                    "action": "end",
                    "output": ops,
                }
            )
        )
        return ops

    def get_sub_command(self, query: dict) -> str:
        """
        Decide whether the sub-command is "cerca" or "estrai"
        based on the target (`what`).

        Rule:
        - If target is "entità" → use "cerca".
        - Otherwise → use "estrai".

        Args:
            query (dict): Query definition including `what`.

        Returns:
            str: Sub-command to apply.
        """
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
