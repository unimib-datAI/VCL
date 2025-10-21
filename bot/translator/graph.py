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
import re

from typing import Literal
from typing_extensions import TypedDict

from langgraph.types import Command
from langgraph.graph import StateGraph

from bot.utils.config import Config
from bot.utils.file_manager import remove_empty_values


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
    explicit_documents: list
    implicit_documents: list
    task_documents: list
    
    order: dict
    classes: list
    
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
        
        graph_builder.add_node("documentsParallelizer", self.documents_parallelizer)
        graph_builder.add_node("explicitDocumentsExtraction", self.explicit_documents_extraction)
        graph_builder.add_node("implicitDocumentsExtraction", self.implicit_documents_extraction)
        graph_builder.add_node("taskDocumentsExtraction", self.task_documents_extraction)
        graph_builder.add_node("documentsAggregator", self.documents_aggregator)
        
        graph_builder.add_node("commandRouter", self.command_router)
        
        graph_builder.add_node("limitExtraction", self.limit_extraction)
        graph_builder.add_node("classesExtraction", self.classes_extraction)
        graph_builder.add_node("orderExtraction", self.order_extraction)
    
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
            query = task["prompt"],        # Original query text
            id_user = id_user,    # User identifier
            
            command = {
                "name": task.get("structured_query", {}).get("command", ""),    # Placeholder for generated command
                "description": self.cfg.get_description_from_command(task.get("structured_query", {}).get("command", ""))           # Placeholder for command description
            },
            
            what = {},
            limit = {},
            how = {},
            
            order = {},
            classes = [],
            
            documents = [],               # List of documents retrieved/generated
            explicit_documents = [],
            implicit_documents = [],
            task_documents = task.get("structured_query", {}).get("documents", []),
            
            iteration = 1,  # Tracks rewrite iteration
            feedback = "",
            score = 0
        )
        
    def start_rewriting_graph(self, data, id_user):
        initial_state = self.initial_state(data, id_user)
        config = {"configurable": {"thread_id": id_user}}
        response = self.graph.invoke(initial_state, config=config)
        
        final_response = {
            "command": response["command"]["name"],
            "documents": response["documents"],
        }
        
        for data in [("limit", ["riassumi"]), 
                     ("what", ["cerca", "estrai"]), 
                     ("classes", ["classifica"]), 
                     ("order", ["riorganizza"])]:
            if not response.get(data[0], {}) == {} or final_response.get("command") in data[1]:
                final_response.update({data[0]: response[data[0]]})
        
        how = response.get("how", {})
        for key in how:
            if not how[key] == "":
                if "how" not in final_response:
                    final_response["how"] = {}
                final_response["how"].update({key: how[key]})
        
        return final_response

    # ------------------- NODE DEFINITIONS -------------------
    def intent_classification(
        self, state: State
    ) -> Command[Literal["documentsParallelizer"]]:
        """
        Step 1: Map query intent to a command (e.g. cerca, estrai, calcola).
        """

        command_update = state.get("command", {})
        
        if command_update.get("name", "altro") == "altro" or state.get("iteration", 1) > 1:
            state["feedback"] = self.get_feedback_str(state, "3 - IntentClassification.json")
            
            result = self.llm.invoke_from_file(
                os.path.join(self.project_root, "prompts", "rewriting", "3 - IntentClassification.json"),
                state,
                True
            )
            
            result = self.cfg.get_command_from_key(result)

            command_update = {
                "name": result,
                "description": self.cfg.get_description_from_command(result),
            }
            
            status = "Done"
        else:
            status = "Skipped"
        
        self.logger.info(f"Intent Classification: {command_update.get("name", "altro")} - {status}")
        
        return Command(
            goto="documentsParallelizer",
            update={
                "command": command_update
            },
        )
        
    def documents_parallelizer(
        self, state: State
    ) -> Command[Literal["explicitDocumentsExtraction", "implicitDocumentsExtraction", "taskDocumentsExtraction"]]:
        
        self.logger.info("Document Parallelizer: Starting")
        
        return Command(goto=["explicitDocumentsExtraction", "implicitDocumentsExtraction", "taskDocumentsExtraction"])

    def explicit_documents_extraction(
        self, state: State
    ) -> Command[Literal["documentsAggregator"]]:
        
        explicit_documents = state.get("explicit_documents", [])
        
        if not explicit_documents or state.get("iteration", 1) > 1:
            explicit_documents = self.llm.invoke_from_file(
                os.path.join(self.project_root, "prompts", "rewriting", "4 - ExplicitDocumentsExtraction.json"),
                state,
                True
            )
            
            explicit_documents = self.llm.str_in_list(explicit_documents)
            
            status = "Done"
        else:
            status = "Skipped"
        
        self.logger.info(f"Explicit Documents Extraction: {explicit_documents} - {status}")
        
        return Command(goto="documentsAggregator", update={"explicit_documents": explicit_documents})
    
    def implicit_documents_extraction(
        self, state: State
    ) -> Command[Literal["documentsAggregator"]]:
        
        implicit_documents = state.get("implicit_documents", [])
        
        if not implicit_documents or state.get("iteration", 1) > 1:
            chat = self.storage.read(state["id_user"])
            
            state["chat"] = str(chat)
            
            if not(chat is None or chat == []):
                implicit_documents = self.llm.invoke_from_file(
                    os.path.join(self.project_root, "prompts", "rewriting", "4 - ImplicitDocumentsExtraction.json"),
                    state,
                    True
                )
                
                implicit_documents = self.llm.str_in_list(implicit_documents)
                status = "Done"
            else:
                status = "Skipped (empty chat history)"
        else:
            status = "Skipped"
        
        self.logger.info(f"Implicit Documents Extraction: {implicit_documents} - {status}")
        
        return Command(goto="documentsAggregator", update={"implicit_documents": implicit_documents})
    
    def task_documents_extraction(
        self, state: State
    ) -> Command[Literal["documentsAggregator"]]:
        task_documents = state.get("task_documents", [])
        
        if not task_documents or state.get("iteration", 1) > 1:
            # Regular expression to match [<number>]
            # (\d+) captures one or more digits representing the task ID
            pattern = r"\[(\d+)\]"

            # Find all matches and capture the task number
            task_documents = re.findall(pattern, state["query"])
            
            status = "Done"
        else:
            status = "Skipped"
        
        self.logger.info(f"Task Documents Extraction: {task_documents} - {status}")
            
        return Command(goto="documentsAggregator", update={"task_documents": task_documents})
    
    def documents_aggregator(
        self, state: State
    ) -> Command[Literal["commandRouter"]]:
        
        self.logger.info("Document Parallelizer: Done")
        
        result = state["explicit_documents"] + state["implicit_documents"] + state["task_documents"]
        result = [
            f"task_{str(id).strip()}" if (str(id).strip().isdigit() or isinstance(id, int)) else str(id).strip()
            for id in result
        ]

        result = list(set(result))
        
        self.logger.info(f"Document Aggregator: {result}")
        
        return Command(goto=["commandRouter"], update={"documents": result})
    
    def command_router(self, state: State) -> Command[Literal["additionalConditionsExtraction", 
                                                              "limitExtraction", 
                                                              "whatExtraction",
                                                              "classesExtraction",
                                                              "orderExtraction"]]:
        if state["command"]["name"] in ["cerca", "estrai"]:
            goto = "whatExtraction"
        elif state["command"]["name"] in ["riassumi", "espandi"]:
            goto = "limitExtraction"
        elif state["command"]["name"] == "classifica":
            goto = "classesExtraction"
        elif state["command"]["name"] == "riorganizza":
            goto = "orderExtraction"
        else:
            goto = "additionalConditionsExtraction"
            
        self.logger.info(f"Command Router: {state["command"]["name"]} -> {goto}")
        
        return Command(goto=goto)
    
    def limit_extraction(self, state: State) -> Command[Literal["additionalConditionsExtraction"]]:
        state["feedback"] = self.get_feedback_str(state, "5 - LimitExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "5 - LimitExtraction.json"),
            state,
            True
        )
        result = self.llm.str_in_dict(result)
        
        self.logger.info(f"Limit Extraction: {str(result)} - Done")

        return Command(goto="additionalConditionsExtraction", update={"limit": result})
    
    def classes_extraction(self, state: State) -> Command[Literal["additionalConditionsExtraction"]]:
        state["feedback"] = self.get_feedback_str(state, "5 - ClassesExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "5 - ClassesExtraction.json"),
            state,
            True
        )
        result = self.llm.str_in_list(result)
        
        self.logger.info(f"Classes Extraction: {str(result)} - Done")

        return Command(goto="additionalConditionsExtraction", update={"classes": result})
    
    def order_extraction(self, state: State) -> Command[Literal["additionalConditionsExtraction"]]:
        state["feedback"] = self.get_feedback_str(state, "5 - OrderExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "5 - OrderExtraction.json"),
            state,
            True
        )
        
        result = self.llm.str_in_dict(result)
        
        self.logger.info(f"Order Extraction: {str(result)} - Done")

        return Command(goto="additionalConditionsExtraction", update={"order": result})

    def what_extraction(
        self, state: State
    ) -> Command[Literal["entityDisambiguation", "additionalConditionsExtraction"]]:
        """
        Step 5: Extract 'what' (subject). Can be entity or other.
        """
        state["feedback"] = self.get_feedback_str(state, "6 - WhatExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "6 - WhatExtraction.json"),
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
            
        self.logger.info(f"What Extraction: {str(what)} - Done")

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
                    result = "6a - PersonDisambiguation.json"
                case "organizzazione":
                    result = "6b - OrganizationDisambiguation.json"
                case "denaro":
                    result = "6c - MoneyDisambiguation.json"
                case "fonte":
                    result = "6d - SourcesDisambiguation.json"
                case "luogo":
                    result = "6e - PlacesDisambiguation.json"
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
                
                status = "Done"
            else:
                status = "Skipped (unknown entity type)"
        else:
            status = "Skipped (empty what)"
        
        self.logger.info(f"Entity Disambiguation: {str(new_what)} - {status}")

        return Command(goto="additionalConditionsExtraction", update={"what": new_what})

    def additional_conditions_extraction(
        self, state: State
    ) -> Command[Literal["evaluationResult"]]:
        """
        Step 6: Extract constraints.
        """
        actual_state = dict(copy.deepcopy(state))
        actual_state["query_str"] = self.state_in_str(state)
        actual_state["feedback"] = self.get_feedback_str(actual_state, "7 - AdditionalConditionsExtraction.json")
        
        result = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", "7 - AdditionalConditionsExtraction.json"),
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
            os.path.join(self.project_root, "prompts", "rewriting", "8 - EvaluationResult.json"),
            {"query_str": self.state_in_str(state)},
            True
        )
        
        result = self.llm.str_in_dict(result)
        
        result["voto"] = int(result["voto"]) if result["voto"].isdigit() else 0

        if result["voto"] < self.minimum_score and state["iteration"] < self.cfg.max_iterations:
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
