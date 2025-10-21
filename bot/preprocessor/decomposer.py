import networkx as nx
import os
import threading

from bot.utils.config import Config

class Decomposer():
    _instance = None  # Holds the singleton instance
    _lock = threading.Lock()  # Thread lock for safe initialization
    
    def __init__(self, cfg: Config):
        """
        Initialize the Decompose class.

        Args:
            cfg (Config): The global configuration instance containing logger
                          and other settings.
        """
        
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Decompose")
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
        
    def decompose(self, query: str) -> nx.DiGraph:
        self.logger.info(f"Correction and Decomposition by LLM: Starting")
        
        query = self.llm.invoke_from_file(
            os.path.join(self.project_root, "prompts", "rewriting", f"1 - CorrectionQuery.json"),
            {"query": query}
        )
        
        query_decomposed = self.llm.invoke_from_file(
            os.path.join("prompts", "rewriting", "2 - Decomposition.json"), 
            {"query": query}
        )
        
        query_decomposed = self.llm.str_in_dict(query_decomposed)["subtasks"]
        
        self.logger.info(f"Correction and Decomposition by LLM: Done")
        self.logger.info(f"Building graph: Starting")
        
        DG = self.build_graph(query_decomposed)
        
        self.logger.info(f"Building graph: Done")
        self.logger.info(f"Found {str(DG.number_of_nodes())} subtasks")
        
        return DG
        
    @staticmethod
    def build_graph(tasks: list) -> nx.DiGraph:
        DG = nx.DiGraph()
        
        for task in tasks:
            DG.add_node(task["id"], data={
                    "id": f"task_{task['id']}", 
                    "prompt": task['prompt'], 
                    "structured_query": {
                        "command": task["command"], 
                        "documents": task["dependences"]
                    }
                }
            )
        
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
                "prompt": f"Integra in un'unica risposta i testi delle risposte {sink_nodes_str}",
                "structured_query": {
                    "documents": sink_nodes,
                    "command": "integra"
                }
            }
            
            new_edges = [(node, new_task["id"]) for node in sink_nodes]
            
            DG.add_node(new_task["id"], data=new_task)
            DG.add_edges_from(new_edges)
        
        return DG