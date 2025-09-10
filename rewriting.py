"""
This module defines the Rewriting class, which is responsible for transforming
user queries into a structured, machine-readable format using a Graph-based system.

It provides:
- Rewriting of queries via the `rewrite` method.
- Initialization of a structured state for each query using `initial_state`.
- Logging of all steps for traceability and debugging.

Dependencies:
- utils.config.Config: Provides global configuration and logging.
- graph.Graph: Provides the Graph object used to perform the rewriting.
- graph.State: Provides the State object used in the Graph.
"""

import json
from utils.config import Config
from graph import Graph, State


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
        self.graph = Graph(cfg).graph
        self.logger = cfg.logger

    def rewrite(self, query: str, id_user: str) -> dict:
        """
        Rewrite the input query into a structured form using the Graph.

        Args:
            query (str): The user's original query.
            id_user (str): Identifier for the user or conversation thread.

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

        # Configuration for the Graph invocation
        config = {"configurable": {"thread_id": id_user}}

        # Invoke the graph to perform the rewriting
        response = self.graph.invoke(self.initial_state(query, id_user), config=config)

        # Log the result of the rewriting
        self.logger.info(
            json.dumps(
                {
                    "step": "Rewriting.rewrite",
                    "action": "end",
                    "response": response["response"],
                }
            )
        )

        # Return the structured rewritten response
        return response["response"]

    @staticmethod
    def initial_state(query: str, id_user: str) -> State:
        """
        Create the initial state for the graph invocation.

        Args:
            query (str): The user's original query.
            id_user (str): Identifier for the user or conversation thread.

        Returns:
            State: A dictionary representing the initial state for the Graph.
        """
        return State(
            query=query,  # Original query text
            thread_id=id_user,  # Thread/user identifier
            command="",  # Placeholder for generated command
            description_command="",  # Placeholder for command description
            documents=[],  # List of documents retrieved/generated
            id_result="",  # Result ID
            unit="",  # Optional unit information
            what_name="",  # Type of 'what' requested
            what_type="",  # Optional type of 'entity' requested
            what_description="",  # Optional descriptive fields
            how_section="",  # Section for procedural instructions
            how_data="",  # Data-related instructions
            how_response="",  # Response-related instructions
            iteration=1,  # Tracks rewrite iteration
            feedback="",  # Feedback for iterative improvement
            response={},  # Placeholder for final response
        )
