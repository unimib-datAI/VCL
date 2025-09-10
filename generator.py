import os
import time
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from utils.config import Config
from utils.file_manager import read_file


class Generator:
    path = os.path.join("prompts", "generator")

    def __init__(self, cfg: Config):
        self.llm = cfg.llm
        self.rag = cfg.rag
        self.seconds = cfg.seconds
        self.parsers = StrOutputParser()
        self.logger = cfg.logger

    def generate(self, op: dict, docs: list[dict], query: str) -> str:
        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "start",
                    "operation": op,
                    "user_query": query,
                    "num_docs": len(docs),
                }
            )
        )

        # Caso speciale: richiesta intero documento
        if (op["command"] in ["estrai", "cerca"]) and op["what"][
            "name"
        ] == "intero documento":
            result = "\n\n".join([d["text"] for d in docs]).strip()
            self.logger.info(
                json.dumps(
                    {
                        "step": "Generator.generate",
                        "action": "direct_return",
                        "reason": "full_document",
                        "result_length": len(result),
                    }
                )
            )
            return result

        template = read_file(os.path.join(self.path, f"{op['command']}.json"))
        template["system"] = "\n".join(template["system"])
        template["human"] = "\n".join(template["human"])

        conditions = ""
        if op.get("how", {}):
            conditions = "\nInoltre la risposta deve rispettare le seguenti condizioni:"
            for condition, value in op["how"].items():
                if value:
                    conditions += f"\n- Condizione {condition}: {value}"

        if conditions.strip() and not conditions.endswith(":"):
            template["system"] += f"\n{conditions}"

        context = ""
        for index, doc in enumerate(docs):
            context += f"[Document {index + 1}]\n\n{doc}\n\n"

        prompt = ChatPromptTemplate.from_messages(
            [("system", template["system"]), ("human", template["human"])]
        )
        chain = prompt | self.llm | self.parsers

        result = chain.invoke({"query": query, "context": context})
        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "llm_invoked",
                    "result_preview": result[:200],
                }
            )
        )

        time.sleep(self.seconds)

        self.logger.info(
            json.dumps(
                {
                    "step": "Generator.generate",
                    "action": "end",
                    "result_length": len(result),
                }
            )
        )
        return result
