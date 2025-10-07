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
import copy
import json

from typing import Literal
from typing_extensions import TypedDict

from langgraph.types import Command
from langgraph.graph import StateGraph

from langchain.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate

from utils.config import Config
from utils.file_manager import read_file


class State(TypedDict):
    """
    Typed representation of the graph state.
    Tracks query, extracted features, and intermediate results
    across the rewriting pipeline.
    """

    query: str       # Original query text
    id_user: str    # User identifier
    id_request: str  # Request identifier
    command: dict
    documents: list # List of documents retrieved/generated    
    unit: str    # Optional unit information
    what: dict     
    how: dict
    iteration: int  # Tracks rewrite iteration
    score: int


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
        project_root: Path project
        minimum_score: Minimum rewrite grade needed to complete the process
    """

    def __init__(self, cfg: Config = None):
        """
        Initialize the graph and register nodes.
        """
        if cfg is None:
            cfg = Config.get_instance()

        self.cfg = cfg
        self.logger = cfg.logger
        self.storage = cfg.storage
        self.llm = cfg.llm
        self.project_root = cfg.project_root
        self.minimum_score = cfg.minimum_score

        # Build state graph and register nodes
        graph_builder = StateGraph(State)
        graph_builder.add_node("intentClassification", self.intent_classification)
        graph_builder.add_node("documentExtraction", self.document_extraction)
        graph_builder.add_node("documentDisambiguation", self.document_disambiguation)
        graph_builder.add_node("unitExtraction", self.unit_extraction)
        graph_builder.add_node("whatExtraction", self.what_extraction)
        graph_builder.add_node("entityDisambiguation", self.entity_disambiguation)
        graph_builder.add_node("sectionsConditions", self.sections_conditions)
        graph_builder.add_node("dataConditions", self.data_conditions)
        graph_builder.add_node("responseConditions", self.response_conditions)
        graph_builder.add_node("evaluationResult", self.evaluation_result)
        graph_builder.set_entry_point("intentClassification")

        self.graph = graph_builder.compile()
        
    @staticmethod
    def initial_state(task: dict, id_user: str, id_request: str) -> State:
        """
        Create the initial state for the graph invocation.

        Args:
            query (str): The user's original query.
            id_user (str): Identifier for the user or conversation thread.
            id_request (str): Identifier for the request.

        Returns:
            State: A dictionary representing the initial state for the Graph.
        """
        return State(
            query=task["prompt"],        # Original query text
            id_user=id_user,    # User identifier
            id_request=id_request, # Request identifier
            
            command={
                "name": task["command"],    # Placeholder for generated command
                "description": ""           # Placeholder for command description
            },
            
            documents=[f"{str(id_request)}_{d}" for d in task["dependences"]], # List of documents retrieved/generated
            
            unit="",    # Optional unit information
            
            what = {
                "name": "", # Type of 'what' requested
                "type": "", # Optional type of 'entity' requested
                "description": "" # Optional descriptive fields
            },        
            
            how = {
                "section": "",  # Section for procedural instructions
                "data": "",  # Data-related instructions
                "response": "",  # Response-related instructions
            },
            
            iteration=1,  # Tracks rewrite iteration
            
            score=0
        )
        
    def start_rewriting_graph(self, data, id_user, id_request):
        initial_state = self.initial_state(data, id_user, id_request)
        config = {"configurable": {"thread_id": id_user}}
        response = self.graph.invoke(initial_state, config=config)
        
        final_response = {
            "id": response["id_request"],
            "query": response["query"],
            "command": response["command"]["name"],
            "documents": response["documents"],
            "what": response["what"],
            "how": response["how"]
        }
        
        return final_response

    # ------------------- NODE DEFINITIONS -------------------
    def intent_classification(
        self, state: State
    ) -> Command[Literal["documentExtraction", "unitExtraction"]]:
        print(state)
        """
        Step 1: Map query intent to a command (e.g. cerca, estrai, calcola).
        If the command requires units (calcola), also trigger unit extraction.
        """

        result = state.get("command", {}).get("name", "altro")
        if result == "altro" or state.get("iteration", 1) > 1:
            result = self.llm.invoke_from_file(
                os.path.join(self.project_root, "prompts", "rewriting", "2 - IntentClassification.json"),
                state,
                True
            )
            
            result = self.cfg.get_command_from_key(result)

        goto = ["documentExtraction"]
        if "calcola" in result:
            goto.append("unitExtraction")

        self.logger.info(
            json.dumps(
                {"step": "intentClassification", "result": result, "next_node": goto}
            )
        )
        
        command_update = {
            "name": result,
            "description": self.cfg.get_description_from_command(result),
        }

        return Command(
            goto=goto,
            update={
                "command": command_update
            },
        )

    def document_extraction(
        self, state: State
    ) -> Command[Literal["whatExtraction", "documentDisambiguation"]]:
        print(state)
        """
        Step 3: Extract candidate documents from the query.
        If 'contesto' appears, disambiguation is needed.
        """

        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "3 - DocumentExtraction.json"),
            state,
            True
        )
        result = self.llm.str_in_list(result)

        id_result = self.storage.get_new_id(state["id_user"])

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
        print(state)
        """
        Step 3a: Resolve ambiguity when multiple document contexts exist.
        """

        chat = self.storage.read(state["id_user"])

        if chat:
            doc = self.chain("3a - DocumentDisambiguation", state)
            doc = self.llm.str_in_list(doc)
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
        print(state)
        """
        Step 3: Extract unit of measurement (only for 'calcola' commands).
        """

        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "4 - UnitsExtraction.json"),
            state,
            True
        )

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
        print(state)
        """
        Step 5: Extract 'what' (subject). Can be entity or other.
        """

        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "5 - WhatExtraction.json"),
            state,
            True
        )

        if result in [
            "persona",
            "organizzazione",
            "luogo",
            "denaro",
            "fonte",
            "articolo",
        ]:
            goto, what = "entityDisambiguation", {"name": 'entità', "type": result, "description": ""}
        else:
            goto, what = "sectionsConditions", {"name": result, "type": "", "description": ""}

        self.logger.info(
            json.dumps({"step": "whatExtraction", "result": what["name"], "next_node": goto})
        )

        return Command(
            goto=goto, update={"what": what}
        )

    def entity_disambiguation(
        self, state: State
    ) -> Command[Literal["sectionsConditions"]]:
        print(state)
        """
        Step 5a: Disambiguate entities depending on type (person, organization, etc.).
        """
        new_what = state.get("what", {})
        
        if not new_what == {}:
            result = ""
            match state["what"]["type"]:
                case "persona":
                    result = "5a - PersonDisambiguation.json"
                case "organizzazione":
                    result = "5b - OrganizationDisambiguation.json"
                case "denaro":
                    result = "5c - MoneyDisambiguation.json"
                case "fonte":
                    result = "5d - SourcesDisambiguation.json"
                case "luogo":
                    result = "5e - PlacesDisambiguation.json"
                case _:
                    result = ""
                    
            if not result == "":
                result = self.llm.invoke_from_file(os.path.join(self.project_root, "prompts", "rewriting", result), state, True)

                self.logger.info(
                    json.dumps(
                        {
                            "step": "entityDisambiguation",
                            "result": result,
                            "next_node": "sectionsConditions",
                        }
                    )
                )
                
                new_what.update({'description': result})

        return Command(goto="sectionsConditions", update={"what": new_what})

    def sections_conditions(
        self, state: State
    ) -> Command[Literal["dataConditions"]]:
        print(state)
        """
        Step 6: Extract constraints about document sections.
        """
        new_how = state.get("how", {})
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "6 - SectionsConditions.json"),
            state,
            True
        )

        self.logger.info(
            json.dumps(
                {
                    "step": "sectionsConditions",
                    "result": result,
                    "next_node": "dataConditions",
                }
            )
        )
        
        new_how.update({"section": result})

        return Command(
            goto="dataConditions",
            update={"how": new_how},
        )

    def data_conditions(self, state: State) -> Command[Literal["responseConditions"]]:
        print(state)
        """
        Step 6a: Extract constraints about data requirements.
        """
        new_how = state.get("how", {})
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "6a - DataConditions.json"),
            state,
            True
        )

        self.logger.info(
            json.dumps(
                {"step": "dataConditions", "result": result, "next_node": "evaluationResult"}
            )
        )

        new_how.update({"data": result})
        
        return Command(
            goto="responseConditions", 
            update={"how": new_how},)

    def response_conditions(self, state: State) -> Command[Literal["evaluationResult"]]:
        print(state)
        """
        Step 6b: Extract constraints about response formatting.
        """
        new_how = state.get("how", {})
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "6b - ResponseConditions.json"),
            state,
            True
        )

        self.logger.info(
            json.dumps(
                {
                    "step": "responseConditions",
                    "result": result,
                    "next_node": "evaluationResult",
                }
            )
        )

        new_how.update({"response": result})
        
        return Command(
            goto="evaluationResult", 
            update={"how": new_how},
        )

    def evaluation_result(
        self, state: State
    ) -> Command[Literal["intentClassification", "__end__"]]:
        print(state)
        """
        Step 8: Evaluate the generated response.
        - If score < threshold, reiterate pipeline (max iterations).
        - Otherwise, terminate with final result.
        """
        previous_iteration = copy.deepcopy(state)
        previous_score = state["score"]
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "7 - EvaluationResult.json"),
            state,
            True
        )
        
        result = self.llm.str_in_dict(result)
        
        result["voto"] = int(result["voto"]) if result["voto"].isdigit() else 0

        if result["voto"] < self.minimum_score and state["iteration"] <= self.cfg.max_iterations:
            if not previous_iteration == {} and result["voto"] <= previous_score:
                # Avoid infinite loops if no improvement
                goto, action = "__end__", "end"
            else:
                goto, action = "intentClassification", "reiterate"
        else:
            goto, action = "__end__", "end"

        self.logger.info(
            json.dumps(
                {
                    "step": "evaluationResult",
                    "score": result["voto"],
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
                "previous_iteration": previous_iteration
            },
        )
