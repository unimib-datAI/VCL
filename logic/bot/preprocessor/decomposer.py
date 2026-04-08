import networkx as nx
import os
import threading

from utils.config import Config

class Decomposer():
    """
    Handles the decomposition of complex user queries into a sequence of atomic tasks.
    
    This class identifies dependencies between sub-questions and uses a Directed Acyclic 
    Graph (DAG) to ensure tasks are executed in the correct logical order. It implements 
    a Singleton pattern to manage LLM resources efficiently.
    """
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config, request_id):
        """
        Initialize the Decomposer with configuration and resources.

        Args:
            cfg (Config): The global configuration object providing access to
                          the LLM instance, paths, and language settings.
        """
        self._cfg = cfg
        self._llm = cfg.get_LLM()
        self._project_root = cfg.project_root
        self._dql_language = cfg.get_DQL()
        
        self.docs_in_string = cfg.docs_in_string
        
        self._logger = cfg.get_logger("Decomposer", request_id)
        
    @classmethod
    def get_instance(cls, cfg: Config):
        """
        Retrieve the singleton instance of Decomposer, creating it if necessary.

        Args:
            cfg (Config): The configuration instance.

        Returns:
            Decomposer: The singleton instance.
        """
        if cls._instance is None:
            with cls._lock:  # Ensure thread-safe initialization
                if cls._instance is None:
                    cls._instance = cls(cfg)
        return cls._instance
        
    def decompose(self, query: str, request_id: str) -> list:
        """
        Main entry point for query decomposition.
        
        The process involves:
            1. Calling the LLM to identify sub-tasks and dependencies.
            2. Building a dependency graph to order tasks (Topological Sort).
            3. Generating unique IDs for each task within the request scope.

        Args:
            query (str): The raw input query.
            request_id (str): The unique identifier for the current request.

        Returns:
            list: A list of ordered dictionaries representing the structured tasks.
        """
        status = "Error"

        try:
            # Step 1: Fetch the specialized prompt for decomposition
            prompt = self._dql_language.prompts.get("it", {}).get("Decomposition.json", None)
            
            if not prompt:
                raise ValueError("Decomposition prompt not found in language config.")
            
            if query.strip():
                # Step 2: Use LLM to extract tasks and their relationships
                # The result is expected to be a structured list of dicts
                result = self._llm.invoke(
                    prompt,
                    { "query": query },
                    True
                )
                
                # Step 3: Apply graph logic to sort tasks by dependency
                result = self.order_tasks(result, request_id)
                
                if len(result) == 0:
                    raise Exception("0 task detected")
                
                status = "Done"
            else:
                raise ValueError("Empty query provided.")

        except Exception as e:
            # Fallback: In case of error, treat the whole query as a single task
            self._logger.error(f"Error during query decomposition: {e}")
            result = [
                {
                    "id": "1",
                    "prompt": query,
                    "structured_prompt": {}
                }
            ]
            
        self._logger.info(f"Decomposition result: {len(result)} tasks created - {status}")
        
        # Format the final task list with unique request-based IDs
        return [
            {
                "id": f"{request_id}_{str(q.get('id', str(i)))}",
                "prompt": q.get("prompt", ""),
                "structured_prompt": q.get("structured_prompt", {})
            }
            for i, q in enumerate(result, start=1)
        ]
        
    def order_tasks(self, tasks: list, request_id: str) -> list:
        """
        Builds a Directed Acyclic Graph (DAG) to sort tasks based on their dependencies.
        
        If multiple terminal (sink) nodes are found, a final 'integration' task 
        is automatically generated to merge all previous results into a single answer.

        Args:
            tasks (list): Raw list of tasks with 'id' and 'dependences'.
            request_id (str): The unique identifier for the current request.

        Returns:
            list: Tasks ordered by topological sort.
        """
        DG = nx.DiGraph()
        
        # Step 1: Build nodes and edges for the dependency graph
        list_edge = []
        for task in tasks:
            task_id = str(task.get('id', ''))
            DG.add_node(
                task_id, 
                data={
                    "id": task_id, 
                    "prompt": task.get('prompt', ''),
                    "structured_prompt": {}
                }
            )
            
            # Map 'dependences' to graph edges (source -> target)
            for dependence in task.get('dependences', []):
                edge = (str(dependence), task_id)
                if edge not in list_edge:
                    list_edge.append(edge)
                    
        DG.add_edges_from(list_edge)
        
        # Step 2: Identify terminal tasks (nodes with no outgoing edges)
        sink_nodes = [n for n in DG.nodes if DG.out_degree(n) == 0]
        
        # Step 3: Auto-generate an integration task if the reasoning branches out
        if len(sink_nodes) > 1:
            sink_nodes_str = ", ".join([f"#{s}" for s in sink_nodes])
            new_id = str(len(tasks) + 1)
            
            new_task_data = {
                "id": new_id, 
                "prompt": f"Integra {sink_nodes_str}",
                "from": [[f"{request_id}_{str(s)}", f"#{str(s)}"] for s in sink_nodes],
                "structured_prompt": {
                    "command": "integra",
                    "from": [[f"{request_id}_{str(s)}", f"#{str(s)}"] for s in sink_nodes],
                    "what": [{"name": "intero documento"}]
                }
            }
            
            # Connect all sink nodes to the final integration node
            new_edges = [(node, new_id) for node in sink_nodes]
            
            DG.add_node(new_id, data=new_task_data)
            DG.add_edges_from(new_edges)
        
        # Step 4: Perform topological sort to get a linear execution order
        ordered_ids = list(nx.topological_sort(DG))
        ordered_prompts = [DG.nodes[n]["data"] for n in ordered_ids]
        
        return ordered_prompts