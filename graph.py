import os
import time
import json

from pathlib import Path
from typing import Literal
from typing_extensions import TypedDict

from langgraph.types import Command
from langgraph.graph import StateGraph

from langchain.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from utils.config import Config
from utils.file_manager import read_file


class State(TypedDict):
    query: str
    thread_id: str

    command: str
    description_command: str

    documents: list[str]
    id_result: str

    unit: str

    what_name: str
    what_type: str
    what_description: str

    section_condition: str
    data_condition: str
    response_condition: str

    iteration: int
    feedback: str
    response: dict


class Graph:
    def __init__(self, cfg: Config = None):
        self.project_root = Path(__file__).resolve().parent

        if cfg is None:
            cfg = Config.get_instance()

        self.cfg = cfg
        self.logger = self.cfg.logger
        self.storage = self.cfg.storage
        self.llm = self.cfg.llm

        graph_builder = StateGraph(State)
        graph_builder.add_node("correctionQuery", self.correction_query)
        graph_builder.add_node("intentClassification", self.intent_classification)
        graph_builder.add_node("documentExtraction", self.document_extraction)
        graph_builder.add_node("documentDisambiguation", self.document_disambiguation)
        graph_builder.add_node("unitExtraction", self.unit_extraction)
        graph_builder.add_node("whatExtraction", self.what_extraction)
        graph_builder.add_node("entityDisambiguation", self.entity_disambiguation)
        graph_builder.add_node("sectionsConditions", self.sections_conditions)
        graph_builder.add_node("dataConditions", self.data_conditions)
        graph_builder.add_node("responseConditions", self.response_conditions)
        graph_builder.add_node("aggregator", self.aggregator)
        graph_builder.add_node("evaluationResult", self.evaluation_result)
        graph_builder.set_entry_point("correctionQuery")

        self.graph = graph_builder.compile()

    def correction_query(
        self, state: State
    ) -> Command[Literal["intentClassification"]]:
        self.logger.info(
            json.dumps(
                {
                    "step": "correctionQuery",
                    "iteration": state["iteration"],
                    "action": "start",
                }
            )
        )
        result = self.chain("1 - CorrectionQuery", state)
        self.logger.info(
            json.dumps(
                {
                    "step": "correctionQuery",
                    "result": result,
                    "next_node": "intentClassification",
                }
            )
        )
        return Command(goto="intentClassification", update={"query": result})

    def intent_classification(
        self, state: State
    ) -> Command[Literal["documentExtraction", "unitExtraction"]]:
        result = self.chain("2 - IntentClassification", state)
        result = self.cfg.get_command_from_key(result)
        goto = ["documentExtraction"]
        if "calcola" in result:
            goto.append("unitExtraction")
        self.logger.info(
            json.dumps(
                {"step": "intentClassification", "result": result, "next_node": goto}
            )
        )
        return Command(
            goto=goto,
            update={
                "command": result,
                "description_command": self.cfg.get_description_from_command(result),
            },
        )

    def document_extraction(
        self, state: State
    ) -> Command[Literal["whatExtraction", "documentDisambiguation"]]:
        result = self.chain("3 - DocumentExtraction", state)
        result = self.cfg.str_in_list(result)

        goto = "whatExtraction"
        if "contesto" in result:
            goto = "documentDisambiguation"

        id_result = self.storage.get_new_id(state["thread_id"])

        self.logger.info(
            json.dumps(
                {"step": "documentExtraction", "result": result, "next_node": goto}
            )
        )
        return Command(
            goto=goto,
            update={"documents": result, "id_result": id_result},
        )

    def document_disambiguation(
        self, state: State
    ) -> Command[Literal["whatExtraction"]]:
        chat = self.storage.read(state["thread_id"])
        if chat:
            doc = self.chain("3a - DocumentDisambiguation", state)
            doc = self.cfg.str_in_list(doc)
        else:
            doc = [
                "sentenza di primo grado",
                "sentenza di secondo grado",
                "memoria giudiziale",
                "ricorso giudiziale",
            ]
        self.logger.info(
            json.dumps(
                {
                    "step": "documentDisambiguation",
                    "result": doc,
                    "next_node": "whatExtraction",
                }
            )
        )
        return Command(goto="whatExtraction", update={"documents": doc})

    def unit_extraction(self, state: State) -> Command[Literal["whatExtraction"]]:
        result = self.chain("4 - UnitsExtraction", state)
        self.logger.info(
            json.dumps(
                {
                    "step": "unitExtraction",
                    "result": result,
                    "next_node": "whatExtraction",
                }
            )
        )
        return Command(goto="whatExtraction", update={"unit": result})

    def what_extraction(
        self, state: State
    ) -> Command[Literal["entityDisambiguation", "sectionsConditions"]]:
        result = self.chain("5 - WhatExtraction", state)
        what_name, what_type = "", ""
        if result in [
            "persona",
            "organizzazione",
            "luogo",
            "denaro",
            "fonte",
            "articolo",
        ]:
            what_name = "entità"
            what_type = result
            goto = "entityDisambiguation"
        else:
            what_name = result
            goto = "sectionsConditions"
        self.logger.info(
            json.dumps({"step": "whatExtraction", "result": result, "next_node": goto})
        )
        return Command(
            goto=goto, update={"what_name": what_name, "what_type": what_type}
        )

    def entity_disambiguation(
        self, state: State
    ) -> Command[Literal["sectionsConditions"]]:
        result = ""
        match state["what_type"]:
            case "persona":
                result = self.chain("5a - PersonDisambiguation", state)
            case "organizzazione":
                result = self.chain("5b - OrganizationDisambiguation", state)
            case "denaro":
                result = self.chain("5c - MoneyDisambiguation", state)
            case "fonte":
                result = self.chain("5d - SourcesDisambiguation", state)
            case "luogo":
                result = self.chain("5e - PlacesDisambiguation", state)
        self.logger.info(
            json.dumps(
                {
                    "step": "entityDisambiguation",
                    "result": result,
                    "next_node": "sectionsConditions",
                }
            )
        )
        return Command(goto="sectionsConditions", update={"what_description": result})

    def sections_conditions(
        self, state: State
    ) -> Command[Literal["dataConditions", "responseConditions"]]:
        result = self.chain("6 - SectionsConditions", state)
        self.logger.info(
            json.dumps(
                {
                    "step": "sectionsConditions",
                    "result": result,
                    "next_node": ["dataConditions", "responseConditions"],
                }
            )
        )
        return Command(
            goto=["dataConditions", "responseConditions"],
            update={"section_condition": result},
        )

    def data_conditions(self, state: State) -> Command[Literal["aggregator"]]:
        result = self.chain("6a - DataConditions", state)
        self.logger.info(
            json.dumps(
                {"step": "dataConditions", "result": result, "next_node": "aggregator"}
            )
        )
        return Command(goto="aggregator", update={"data_condition": result})

    def response_conditions(self, state: State) -> Command[Literal["aggregator"]]:
        result = self.chain("6b - ResponseConditions", state)
        self.logger.info(
            json.dumps(
                {
                    "step": "responseConditions",
                    "result": result,
                    "next_node": "aggregator",
                }
            )
        )
        return Command(goto="aggregator", update={"response_condition": result})

    def aggregator(self, state: State) -> Command[Literal["evaluationResult"]]:
        response = {
            "query": state["query"],
            "command": state["command"],
            "documents": state["documents"],
            "id": state["id_result"],
        }
        if state["command"] == "calcola":
            response.update({"unit": state["unit"]})

        what = {"name": state["what_name"]}
        if state["what_name"] == "entità":
            what.update(
                {"type": state["what_type"], "description": state["what_description"]}
            )
        response.update({"what": what})

        how = {}
        if state["section_condition"]:
            how.update({"Section": state["section_condition"]})
        if state["data_condition"]:
            how.update({"Data": state["data_condition"]})
        if state["response_condition"]:
            how.update({"Response": state["response_condition"]})
        response.update({"how": how})

        self.logger.info(
            json.dumps(
                {
                    "step": "aggregator",
                    "result": response,
                    "next_node": "evaluationResult",
                }
            )
        )
        return Command(goto="evaluationResult", update={"response": response})

    def evaluation_result(
        self, state: State
    ) -> Command[Literal["intentClassification", "__end__"]]:
        result = self.chain("7 - EvaluationResult", state)
        result = self.cfg.str_in_dict(result)

        if int(result["voto"]) < 8 and state["iteration"] <= self.cfg.max_iteration:
            goto = "intentClassification"
            action = "reiterate"
        else:
            goto = "__end__"
            action = "end"

        self.logger.info(
            json.dumps(
                {
                    "step": "evaluationResult",
                    "score": result["voto"],
                    "feedback": result["motivazione"],
                    "action": action,
                    "next_node": goto,
                }
            )
        )
        return Command(
            goto=goto,
            update={
                "iteration": state["iteration"] + 1,
                "feedback": result["motivazione"],
                "score": result["voto"],
            },
        )

    def chain(self, file: str, state: State) -> str:
        template = read_file(
            os.path.join(self.project_root, "prompts", "rewriting", f"{file}.json")
        )
        template["system"] = "\n".join(template["system"])
        template["human"] = "\n".join(template["human"])

        input_template = {}
        for p in template["params"]:
            if p == "chat":
                chat = self.storage.chat_in_str(state["thread_id"])
                input_template.update({str(p): str(chat)})
            else:
                input_template.update({str(p): str(state[p])})

        if not (state["response"] == {}) and ("EvaluationResult" not in file):
            response_clean = (
                str(state["response"]).replace("{", "{{").replace("}", "}}")
            )
            template[
                "system"
            ] = f"""
                [PROMPT]
                {template['human']}
                
                [FEEDBACK]
                Considera che per la query è già stato generato un possibile output:
                {response_clean}
                
                Questo output ha ricevuto però una valutazione non sufficiente per i nostri standard.
                La motivazione è stata:
                \"{state['feedback']}\"
                
                Non devi riscostruire l'intero output.
                Nella risposta tieni conto del feedback."""

        if template["examples"]:
            example_prompt = ChatPromptTemplate.from_messages(
                [
                    HumanMessagePromptTemplate.from_template("{input}"),
                    AIMessagePromptTemplate.from_template(
                        "Ragionamento: {reasoning}\nRisultato: {output}"
                    ),
                ]
            )
            few_shot_prompt = FewShotChatMessagePromptTemplate(
                example_prompt=example_prompt, examples=template["examples"]
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", template["system"]),
                    few_shot_prompt,
                    ("human", template["human"]),
                ]
            )
        else:
            prompt = ChatPromptTemplate.from_messages(
                [("system", template["system"]), ("human", template["human"])]
            )

        chain = prompt | self.llm | StrOutputParser()
        result = chain.invoke(input_template)
        time.sleep(self.cfg.seconds)

        result = result.lower()
        if "risultato:" in result:
            result = result[result.index("risultato:") + 11 :]
        if result == "''":
            result = ""
        return result.strip()
