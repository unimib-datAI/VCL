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

from utils.config import Config
from utils.file_manager import remove_empty_values


class State(TypedDict):
    """
    Typed representation of the graph state.
    Tracks query, extracted features, and intermediate results
    across the rewriting pipeline.
    """

    query: str       # Original query text
    id_user: str    # User identifier
    command: dict
    documents: list # List of documents retrieved/generated
    
    what: dict
    limit: dict
    how: dict
    
    iteration: int  # Tracks rewrite iteration
    feedback: str
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
        self.logger = cfg.get_logger("Graph")
        self.storage = cfg.storage
        self.llm = cfg.llm
        self.project_root = cfg.project_root
        self.minimum_score = cfg.minimum_score

        # Build state graph and register nodes
        graph_builder = StateGraph(State)
        graph_builder.add_node("intentClassification", self.intent_classification)
        
        graph_builder.add_node("documentExtraction", self.document_extraction)
        graph_builder.add_node("documentDisambiguation", self.document_disambiguation)
        
        graph_builder.add_node("commandRouter", self.command_router)
        
        graph_builder.add_node("limitExtraction", self.limit_extraction)
    
        graph_builder.add_node("whatExtraction", self.what_extraction)
        graph_builder.add_node("entityDisambiguation", self.entity_disambiguation)
       
        graph_builder.add_node("additionalConditionsExtraction", self.additional_conditions_extraction)
        
        graph_builder.add_node("evaluationResult", self.evaluation_result)
        
        graph_builder.set_entry_point("intentClassification")
        self.graph = graph_builder.compile()
        
    def initial_state(self, task: dict, id_user: str) -> State:
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
            
            command={
                "name": task["structured_query"]["command"],    # Placeholder for generated command
                "description": self.cfg.get_description_from_command(task["structured_query"]["command"])           # Placeholder for command description
            },
            
            what={},
            limit={},
            how={},
            
            documents=task["structured_query"]["documents"], # List of documents retrieved/generated
            
            iteration=1,  # Tracks rewrite iteration
            feedback="",
            score=0
        )
        
    def start_rewriting_graph(self, data, id_user):
        initial_state = self.initial_state(data, id_user)
        config = {"configurable": {"thread_id": id_user}}
        response = self.graph.invoke(initial_state, config=config)
        
        final_response = {
            "command": response["command"]["name"],
            "documents": response["documents"],
        }

        limit = response.get("limit", {})
        if not limit == {}:
            final_response.update({"limit": limit})
            
        what = response.get("what", {})
        if not what == {}:
            final_response.update({"what": what})
            
        how = response.get("how", {})
        if not how == {}:
            final_response.update({"how": how})
        
        return remove_empty_values(final_response)

    # ------------------- NODE DEFINITIONS -------------------
    def intent_classification(
        self, state: State
    ) -> Command[Literal["documentExtraction"]]:
        """
        Step 1: Map query intent to a command (e.g. cerca, estrai, calcola).
        """

        command_update = state.get("command", {})
        
        if command_update.get("name", "altro") == "altro" or state.get("iteration", 1) > 1:
            state["feedback"] = self.get_feedback_str(state, "2 - IntentClassification.json")
            
            result = self.llm.invoke_from_file(
                os.path.join(self.project_root, "prompts", "rewriting", "2 - IntentClassification.json"),
                state,
                True
            )
            
            result = self.cfg.get_command_from_key(result)

            self.logger.info(f"Intent Classification: Done")
            self.logger.info(f"\tResult: {result}")
            
            command_update = {
                "name": result,
                "description": self.cfg.get_description_from_command(result),
            }
        else:
            self.logger.info(f"Intent Classification: Skipped (at the moment the result of the decomposition phase is sufficient)")
            self.logger.info(f"\tResult: {command_update.get("name", "altro")}")
        
        return Command(
            goto="documentExtraction",
            update={
                "command": command_update
            },
        )

    def document_extraction(
        self, state: State
    ) -> Command[Literal["commandRouter", "documentDisambiguation"]]:
        """
        Step 3: Extract candidate documents from the query.
        If 'contesto' appears, disambiguation is needed.
        """
        state["feedback"] = self.get_feedback_str(state, "3 - DocumentExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "3 - DocumentExtraction.json"),
            state,
            True
        )
        result = self.llm.str_in_list(result)

        id_result = self.storage.get_new_id(state["id_user"])

        goto = (
            "commandRouter" if "contesto" not in result else "documentDisambiguation"
        )

        self.logger.info(
            json.dumps(
                {"step": "documentExtraction", "result": result, "next_node": goto}
            )
        )

        return Command(goto=goto, update={"documents": result, "id_result": id_result})

    def document_disambiguation(
        self, state: State
    ) -> Command[Literal["commandRouter"]]:
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

        return Command(goto="commandRouter", update={"documents": doc})
    
    def command_router(self, state: State) -> Command[Literal["additionalConditionsExtraction", "limitExtraction"]]:
        if state["command"]["name"] in ["cerca", "estrai"]:
            goto = "whatExtraction"
        elif state["command"]["name"] in ["riassumi", "espandi"]:
            goto = "limitExtraction"
        else:
            goto = "additionalConditionsExtraction"
            
        self.logger.info(f"Command Router: {state["command"]["name"]} -> {goto}")
        
        return Command(goto=goto)
    
    def limit_extraction(self, state: State) -> Command[Literal["additionalConditionsExtraction"]]:
        state["feedback"] = self.get_feedback_str(state, "4 - LimitExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "4 - LimitExtraction.json"),
            state,
            True
        )
        result = self.llm.str_in_dict(result)

        return Command(goto="additionalConditionsExtraction", update={"limit": result})

    def what_extraction(
        self, state: State
    ) -> Command[Literal["entityDisambiguation", "additionalConditionsExtraction"]]:
        """
        Step 5: Extract 'what' (subject). Can be entity or other.
        """
        state["feedback"] = self.get_feedback_str(state, "5 - WhatExtraction.json")
        
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
            goto, what = "additionalConditionsExtraction", {"name": result, "type": "", "description": ""}

        return Command(
            goto=goto, update={"what": what}
        )

    def entity_disambiguation(
        self, state: State
    ) -> Command[Literal["additionalConditionsExtraction"]]:
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
                state["feedback"] = self.get_feedback_str(state, result)
                
                result = self.llm.invoke_from_file(os.path.join(self.project_root, "prompts", "rewriting", result), state, True)

                self.logger.info(
                    json.dumps(
                        {
                            "step": "entityDisambiguation",
                            "result": result,
                            "next_node": "additionalConditionsExtraction",
                        }
                    )
                )
                
                new_what.update({'description': result})

        return Command(goto="additionalConditionsExtraction", update={"what": new_what})

    def additional_conditions_extraction(
        self, state: State
    ) -> Command[Literal["evaluationResult"]]:
        """
        Step 6: Extract constraints.
        """
        actual_state = dict(copy.deepcopy(state))
        actual_state["query_str"] = self.state_in_str(state)
        actual_state["feedback"] = self.get_feedback_str(actual_state, "6 - AdditionalConditionsExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "6 - AdditionalConditionsExtraction.json"),
            actual_state,
            True
        )
        
        result = remove_empty_values(self.llm.str_in_dict(result))

        self.logger.info(f"Additional Conditions Extraction: found {len(list(result.keys()))} conditions")
        for key, value in result.items():
            self.logger.info(f"\t- {key}: {value}")
                             
        return Command(
            goto="evaluationResult",
            update={"how": result},
        )

    def evaluation_result(
        self, state: State
    ) -> Command[Literal["intentClassification", "__end__"]]:
        """
        Step 8: Evaluate the generated response.
        - If score < threshold, reiterate pipeline (max iterations).
        - Otherwise, terminate with final result.
        """
        previous_iteration = copy.deepcopy(state)
        previous_score = state["score"]
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "7 - EvaluationResult.json"),
            {"query_str": self.state_in_str(state)},
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
            
        self.logger.info(f"Evaluation Result: from {previous_score} to {result["voto"]} -> {action}")

        return Command(
            goto=goto,
            update={
                "iteration": state["iteration"] + 1,
                "previous_iteration_comment": result["motivazione"],
                "score": result["voto"],
                "previous_iteration": previous_iteration
            },
        )
    
    @staticmethod
    def state_in_str(state: State) -> str:
        """
        Generate a human-readable string representation of the current state.

        Args:
            state (State): The state dictionary to stringify.

        Returns:
            str: A descriptive summary of the current state.
        """
        result = []

        if state.get("query"):
            result.append(f'- Original question: "{state["query"]}"')

        if state.get("command", {}).get("name"):
            result.append(f'- Identified command: "{state["command"]["name"]}"')

        if state.get("documents"):
            result.append(f'- Retrieved documents: {state["documents"]}')

        if state.get("what"):
            result.append(f'- Target element: {state["what"]}')

        if state.get("limit"):
            result.append(f'- Response length constraint: {state["limit"]}')

        if state.get("how"):
            how = state["how"]
            if how.get("section"):
                result.append(f'- Section condition: "{how["section"]}"')
            if how.get("data"):
                result.append(f'- Data condition: "{how["data"]}"')
            if how.get("response"):
                result.append(f'- Response condition: "{how["response"]}"')

        return "\n".join(result)
    
    @staticmethod
    def get_feedback_str(state, file_name):
        feedback = ""
        # Add feedback loop context if previous iteration failed
        if "previous_iteration" in state.keys() and not (state["previous_iteration"] == {}) and ("EvaluationResult" not in file_name):
            old_response = state["previous_iteration"][state["output"]]
            
            if "entità" in old_response:
                old_response = state["previous_iteration"]["what_type"]
                            
            feedback = f"""
            [FEEDBACK]
            Considera che per la query è già stato generato un possibile output:
            \"{str(old_response)}\"
            
            Questo output ha ricevuto però una valutazione non sufficiente per i nostri standard.
            La motivazione è stata:
            \"{state['previous_iteration_comment']}\".
            
            Non devi ricostruire l'intero output.
            Nella risposta tieni conto del feedback."""
            
        return feedback
