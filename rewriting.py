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

import networkx as nx

import threading

import matplotlib.pyplot as plt

from graph import Graph
from utils.config import Config


class Rewriting:
    """
    Handles the rewriting of user queries using a Graph-based approach.

    Attributes:
        graph (Graph): The Graph object responsible for query processing.
        logger (Logger): Logger instance from the configuration for logging steps.
    """
    
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization

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
        self.logger = cfg.get_logger("Rewriting")
        self.project_root = cfg.project_root
        
    @classmethod
    def get_instance(cls, cfg: Config):
        """
        Retrieve the singleton instance of Config, creating it if necessary.

        Args:
            opts (argparse.Namespace, optional): Parsed command-line options.

        Returns:
            Config: The singleton instance of the configuration.
        """
        if cls._instance is None:
            with cls._lock:  # Ensure thread-safe initialization
                if cls._instance is None:
                    cls._instance = cls(cfg)
        return cls._instance

    def rewrite(self, query_data: dict, id_user: str) -> dict:
        """
        Rewrite the input query into a structured form using the Graph.

        Args:
            query (str): The user's original query.
            id_user (str): Identifier for the user or conversation thread.
            id_request (str): Identifier for the request.

        Returns:
            dict: The rewritten query in a structured dictionary format.
        """
        
        # Invoke the graph to perform the rewriting
        response = self.graph.start_rewriting_graph(query_data, id_user)

        # Return the structured rewritten response
        return response
