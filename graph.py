"""
Graph module for orchestrating query rewriting and interpretation.

This module builds a LangGraph `StateGraph` to process user queries through
a pipeline of LLM-based nodes:
1. Correction of the raw query.
2. Intent classification and command mapping.
3. Document extraction and disambiguation.
4. Unit and entity extraction (for specific intents).
5. Handling of "what" (the subject of the query).
6. Extraction of procedural/data/response conditions.
7. Aggregation into a structured response.
8. Evaluation loop for iterative refinement.

Each node in the graph corresponds to a method of the `Graph` class, and
state transitions are logged in structured JSON for full traceability.
"""

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
    """
    Typed representation of the graph state.
    Tracks query, extracted features, and intermediate results
    across the rewriting pipeline.
    """

    query: str  # Original query text
    thread_id: str  # Thread/user identifier
    command: str  # Generated command
    description_command: str  # Command description
    documents: list[str]  # Candidate/retrieved documents
    id_result: str  # Unique result identifier
    unit: str  # Unit of measurement (if relevant)
    what_name: str  # Type of "what" requested
    what_type: str  # Entity type (if applicable)
    what_description: str  # Description of the entity
    section_condition: str  # Constraints on document sections
    data_condition: str  # Constraints on data
    response_condition: str  # Constraints on response formatting
    iteration: int  # Iteration count for evaluation loop
    feedback: str  # Feedback from evaluator
    response: dict  # Final structured response


class Graph:
    """
    Query rewriting graph using LangGraph.

    Responsibilities:
    - Define nodes (steps in the rewriting pipeline).
    - Manage state transitions via `Command`.
    - Invoke LLM prompts stored under `prompts/rewriting/`.
    - Support iterative refinement with evaluation and feedback.

    Attributes:
        cfg (Config): Shared application configuration.
        logger: Logger for structured JSON logs.
        storage: Storage layer (Redis).
        llm: Chat model (LangChain interface).
        graph: Compiled LangGraph pipeline.
    """

    def __init__(self, cfg: Config = None):
        """
        Initialize the graph and register nodes.
        """
        self.project_root = Path(__file__).resolve().parent
        if cfg is None:
            cfg = Config.get_instance()

        self.cfg = cfg
        self.logger = cfg.logger
        self.storage = cfg.storage
        self.llm = cfg.llm

        # Build state graph and register nodes
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

    # ------------------- NODE DEFINITIONS -------------------

    def correction_query(
        self, state: State
    ) -> Command[Literal["intentClassification"]]:
        """
        Step 1: Normalize/correct the user query before classification.
        """

        self.logger.info(f"{'-'*10}{state['iteration']}{'-'*10}")

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
        """
        Step 2: Map query intent to a command (e.g. cerca, estrai, calcola).
        If the command requires units (calcola), also trigger unit extraction.
        """

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
        """
        Step 3: Extract candidate documents from the query.
        If 'contesto' appears, disambiguation is needed.
        """

        result = self.chain("3 - DocumentExtraction", state)
        result = self.cfg.str_in_list(result)

        id_result = self.storage.get_new_id(state["thread_id"])

        goto = (
            "whatExtraction" if "contesto" not in result else "documentDisambiguation"
        )

        self.logger.info(
            json.dumps(
                {"step": "documentExtraction", "result": result, "next_node": goto}
            )
        )

        return Command(goto=goto, update={"documents": result, "id_result": id_result})

    def document_disambiguation(
        self, state: State
    ) -> Command[Literal["whatExtraction"]]:
        """
        Step 3a: Resolve ambiguity when multiple document contexts exist.
        """

        chat = self.storage.read(state["thread_id"])

        if chat:
            doc = self.chain("3a - DocumentDisambiguation", state)
            doc = self.cfg.str_in_list(doc)
        else:
            # Default fallback set of documents
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
        """
        Step 4: Extract unit of measurement (only for 'calcola' commands).
        """

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
        """
        Step 5: Extract 'what' (subject). Can be entity or other.
        """

        result = self.chain("5 - WhatExtraction", state)

        if result in [
            "persona",
            "organizzazione",
            "luogo",
            "denaro",
            "fonte",
            "articolo",
        ]:
            goto, what_name, what_type = "entityDisambiguation", "entità", result
        else:
            goto, what_name, what_type = "sectionsConditions", result, ""

        self.logger.info(
            json.dumps({"step": "whatExtraction", "result": result, "next_node": goto})
        )

        return Command(
            goto=goto, update={"what_name": what_name, "what_type": what_type}
        )

    def entity_disambiguation(
        self, state: State
    ) -> Command[Literal["sectionsConditions"]]:
        """
        Step 5a: Disambiguate entities depending on type (person, organization, etc.).
        """

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
        """
        Step 6: Extract constraints about document sections.
        """

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
        """
        Step 6a: Extract constraints about data requirements.
        """

        result = self.chain("6a - DataConditions", state)

        self.logger.info(
            json.dumps(
                {"step": "dataConditions", "result": result, "next_node": "aggregator"}
            )
        )

        return Command(goto="aggregator", update={"data_condition": result})

    def response_conditions(self, state: State) -> Command[Literal["aggregator"]]:
        """
        Step 6b: Extract constraints about response formatting.
        """

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
        """
        Step 7: Aggregate partial results into a structured response.
        """

        response = {
            "query": state["query"],
            "command": state["command"],
            "documents": state["documents"],
            "id": state["id_result"],
        }

        if state["command"] == "calcola":
            response.update({"unit": state["unit"]})

        # Build "what" section
        what = {"name": state["what_name"]}
        if state["what_name"] == "entità":
            what.update(
                {"type": state["what_type"], "description": state["what_description"]}
            )

        response.update({"what": what})

        # Build "how" section
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
        """
        Step 8: Evaluate the generated response.
        - If score < threshold, reiterate pipeline (max iterations).
        - Otherwise, terminate with final result.
        """

        result = self.chain("7 - EvaluationResult", state)
        result = self.cfg.str_in_dict(result)

        if int(result["voto"]) < 8 and state["iteration"] <= self.cfg.max_iteration:
            goto, action = "intentClassification", "reiterate"
        else:
            goto, action = "__end__", "end"

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

    # ------------------- UTILS -------------------

    def chain(self, file: str, state: State) -> str:
        """
        Utility to load a prompt JSON, fill parameters, and invoke the LLM.

        Args:
            file (str): Prompt file name (without extension).
            state (State): Current graph state.

        Returns:
            str: Parsed string result from the LLM.
        """
        template = read_file(
            os.path.join(self.project_root, "prompts", "rewriting", f"{file}.json")
        )
        template["system"] = "\n".join(template["system"])
        template["human"] = "\n".join(template["human"])

        # Fill input template from state
        input_template = {}
        for p in template["params"]:
            if p == "chat":
                chat = self.storage.chat_in_str(state["thread_id"])
                input_template.update({str(p): str(chat)})
            else:
                input_template.update({str(p): str(state[p])})

        # Add feedback loop context if previous iteration failed
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
                \"{state['feedback']}\".
                
                Non devi ricostruire l'intero output.
                Nella risposta tieni conto del feedback."""

        # Add few-shot examples if available
        if template["examples"]:
            template["examples"] = [
                {
                    "input": "\n".join(example["input"]),
                    "reasoning": example["reasoning"],
                    "output": example["output"],
                }
                for example in template["examples"]
            ]
            
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

        # Build chain and invoke
        chain = prompt | self.llm | StrOutputParser()
        result = chain.invoke(input_template)
        time.sleep(self.cfg.seconds)

        # Post-process: lower-case, strip unwanted tokens
        result = result.lower()
        if "risultato:" in result:
            result = result[result.index("risultato:") + 11 :]
        if result == "''":
            result = ""
        return result.strip()
