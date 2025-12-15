import networkx as nx
import os
import threading

from utils.config import Config

class Decomposer():
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Decomposer with configuration and resources.

        Args:
            cfg (Config): The global configuration object providing access to
                          the LLM instance, paths, and language settings.
        """
        self._cfg = cfg
        self._llm = cfg.llm
        self._project_root = cfg.project_root
        self._dql_language = cfg.language
        
        self._logger = cfg.get_logger("Decomposer")
        
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
        
    def decompose(self, query: str) -> list:
        status = "Error"

        try:
            # Retrieve the specific prompt for query decomposition
            prompt = self._dql_language.prompts.get("Decomposition.json", None)
            
            if not prompt:
                self._logger.error("Decomposition.json prompt not found.")
                raise ValueError("Error during prompt retrieval")
            
            if query.strip():
                # Invoke LLM to rewrite the query based on the prompt
                result = self._llm.invoke(
                    prompt,
                    { "query": query },
                    True
                )
                
                result = self.order_tasks(result)
                
                status = "Done"
            else:
                raise ValueError("Empty query provided")

        except Exception as e:
            self._logger.error(e)
            result = [
                {
                    "id": "1",
                    "prompt": query
                }
            ] # Return original text on failure
            
        return [
            {
                "id": f"{self._cfg.get_request_id()}_{str(q.get("id", str(i)))}",
                "prompt": q.get("prompt", ""),
                "structured_prompt": {}
            }
            for i, q in enumerate(result, start=1)
        ]
        
    @staticmethod
    def order_tasks(tasks: list) -> nx.DiGraph:
        DG = nx.DiGraph()
        
        list_edge = []
        for task in tasks:
            DG.add_node(
                task.get('id', ''), 
                data={
                    "id": str(task.get('id', '')), 
                    "prompt": task.get('prompt', '')
                }
            )
            
            for dependence in task.get('dependences', []):
                edge = (dependence, task.get('id', ''))
                if edge not in list_edge:
                    list_edge.append(edge)
                    
        DG.add_edges_from(list_edge)
        
        sink_nodes = [n for n in DG.nodes if DG.out_degree(n) == 0]
        
        if len(sink_nodes) > 1:
            sink_nodes_str = ", ".join([f"#{s}" for s in sink_nodes])
            
            new_id = len(tasks) + 1
            
            new_task = {
                "id": str(new_id), 
                "prompt": f"Integra in un'unica risposta i testi delle risposte {sink_nodes_str}"
            }
            
            new_edges = [(node, new_id) for node in sink_nodes]
            
            DG.add_node(new_id, data=new_task)
            DG.add_edges_from(new_edges)
        
        ordered_ids = list(nx.topological_sort(DG))
        ordered_prompts = [DG.nodes[n]["data"] for n in ordered_ids]
        
        return ordered_prompts
    
    @staticmethod
    def docs_in_string(docs):
        info = [
            f"- con la stringa \"{doc[1]}\" l'utente fa riferimento al documento \"{doc[0]}\""
            for doc in docs
            if len(doc) == 2 and doc[0] != doc[1]
        ]
        
        return "\n\t\t".join(info).strip()