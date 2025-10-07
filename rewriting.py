"""
This module defines the Rewriting class, which is responsible for transforming
user queries into a structured, machine-readable format using a Graph-based system.

It provides:
- Rewriting of queries via the `rewrite` method.
- Initialization of a structured state for each query using `initial_state`.
- Logging of all steps for traceability and debugging.

Dependencies:
- graph.Graph: Provides the Graph object used to perform the rewriting.
- graph.State: Provides the State object used in the Graph.
- utils.config.Config: Provides global configuration and logging.
"""

import json
import networkx as nx
import os

import matplotlib.pyplot as plt

from graph import Graph, State
from utils.config import Config


class Rewriting:
    """
    Handles the rewriting of user queries using a Graph-based approach.

    Attributes:
        graph (Graph): The Graph object responsible for query processing.
        logger (Logger): Logger instance from the configuration for logging steps.
    """

    def __init__(self, cfg: Config):
        """
        Initialize the Rewriting class.

        Args:
            cfg (Config): The global configuration instance containing logger
                          and other settings.
        """
        # Initialize the Graph and logger
        self.graph = Graph(cfg)
        self.llm = cfg.llm
        self.logger = cfg.logger
        self.project_root = cfg.project_root

    def rewrite(self, query: str, id_user: str, id_request: str) -> dict:
        """
        Rewrite the input query into a structured form using the Graph.

        Args:
            query (str): The user's original query.
            id_user (str): Identifier for the user or conversation thread.
            id_request (str): Identifier for the request.

        Returns:
            dict: The rewritten query in a structured dictionary format.
        """
        # Log the start of the rewriting process
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
        
        query = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", f"1 - CorrectionQuery.json"),
            {"query": query},
            True
        )
        
        query_decomposed = self.llm.invoke_from_file(
            os.path.join("prompts", "rewriting", "0 - Decomposition.json"), 
            {"query": query}
        )
        query_decomposed = self.llm.str_in_dict(query_decomposed)["subtasks"]
        
        DG = self.build_graph(query_decomposed)
        
        for node in nx.topological_sort(DG):
            # Invoke the graph to perform the rewriting
            response = self.graph.start_rewriting_graph(DG.nodes[node]['data'], id_user, id_request)
            DG.nodes[node]["data"] = {}
            DG.nodes[node]["data"]["query"] = response

        # Return the structured rewritten response
        return DG
        
    def build_graph(self, tasks: list) -> nx.DiGraph:
        DG = nx.DiGraph()
        
        for task in tasks:
            DG.add_node(task["id"], data=task)
        
        list_edge = []
        for task in tasks:
            for dependence in task["dependences"]:
                edge = (dependence, task["id"])
                if edge not in list_edge:
                    list_edge.append(edge)
                    
        DG.add_edges_from(list_edge)
        
        sink_nodes = [n for n in DG.nodes if DG.out_degree(n) == 0]
        
        if len(sink_nodes) > 1:
            sink_nodes_str = ", ".join([f"[{s}]" for s in sink_nodes])
            
            new_task = {
                "id": len(tasks) + 1,
                "command": "integra",
                "prompt": f"Integra in un'unica risposta i testi delle risposte {sink_nodes_str}",
                "depencences": sink_nodes
            }
            
            new_edges = [(d, new_task["id"]) for d in sink_nodes]
            
            DG.add_node(new_task["id"], data=new_task)
            DG.add_edges_from(new_edges)
        
        return DG
