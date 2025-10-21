"""
This module defines a FastAPI application for the DQL system.

It provides an endpoint (/chat) for processing chat messages, which involves:
1. Rewriting the input query using the Rewriting module.
2. Decomposing the rewritten query into operations via the Planner.
3. Retrieving relevant documents and generating answers for each operation.
4. Logging all steps and storing intermediate and final results.
"""

import os
import networkx as nx
from datetime import datetime, timezone

from bot.utils.config import Config
from bot.utils.file_manager import write_file

from bot.preprocessor.preprocessor import Preprocessor
from bot.translator.rewriting import Rewriting
from bot.planner.planner import Planner
from bot.executor.executor import Executor

class Assistant():
    # Load the global configuration
    CFG = Config.get_instance()

    # Initialize components
    rewriting = Rewriting.get_instance(CFG)
    generator = Executor(CFG)
    preprocessor = Preprocessor(CFG)
    planner = Planner(CFG)
    

    logger = CFG.get_logger("Main")

    def chat(self, prompt: str, user_id: str):
        # Log start of chat processing
        self.logger.info(f"Request Received: \"{prompt}\"")
        
        # Set user ID in configuration
        self.CFG.set_user_id(user_id)
        
        # Save id request
        timestamp = str(datetime.now(timezone.utc).isoformat())
        request_id = f"{str(user_id)}_{timestamp}"

        # Step 1: Decompose
        self.logger.info("Step 1 (Preprocessing): Starting")
        prompt = self.preprocessor.process(prompt)
        self.logger.info("Step 1 (Preprocessing): Done")
        
        self.logger.info("Step 2 (Rewriting): Starting")
        structured_query = self.rewriting.rewrite({"prompt": prompt})
        self.logger.info("Step 2 (Rewriting): Done")
        
        try:
            self.logger.info("Step 3 (Planner): Starting")
            operations = self.planner.decompose(structured_query)
            self.logger.info("Step 3 (Planner): Done")
        except Exception as e:
            self.logger.error(f"Planner Error: {e}")
            operations = [structured_query]
        
        for operation in operations:
            self.logger.info(f"Executing operation ID: {operation['id']} with command: {operation['command']}")
            self.logger.info("Step 3 (Retrieval) and Step 4 (Generation): Starting")
            result = self.generator.generate(structured_query)
            self.logger.info("Step 3 (Retrieval) and Step 4 (Generation): Done")
        
        return result
    
    def __init__(self):
        pass
    
#i = 1
#for node in nx.topological_sort(query_graph):
#    node_data = query_graph.nodes[node]["data"]
#    
#    node_data["order"] = i
#    
#    self.logger.info(f"Starting subtask {str(i)}/{str(query_graph.number_of_nodes())}: \"{node_data["prompt"]}\"")
#    
#    # Step 2: Rewriting
#    self.logger.info("Step 2 (Rewriting): Starting")
#    node_data["structured_query"] = self.rewriting.rewrite(node_data, user_id)
#    self.logger.info("Step 2 (Rewriting): Done")
#    
#    # Step 3: Retrieval
#    self.logger.info("Step 3 (Retrieval): Starting")
#    doc = self.retrieval.execute(node_data["structured_query"], query_graph, user_id)
#    self.logger.info("Step 3 (Retrieval): Done")
#    
#    # Step 4: Generation
#    self.logger.info("Step 4 (Generation): Starting")
#    node_data["result"], node_data["structured_query"] = self.generator.generate(node_data["structured_query"], doc, node_data["prompt"])
#    self.logger.info("Step 4 (Generation): Done")
#    
#    query_graph.nodes[node]["data"].update(node_data)
#    
#    i += 1
#    
#final_response = {
#    "id": request_id,
#    "input": query,
#    "tasks": [query_graph.nodes[node]["data"] for node in nx.topological_sort(query_graph)],
#    "result": query_graph.nodes[list(nx.topological_sort(query_graph))[-1]]["data"].get("result", "")
#}
#
#doc_used = [doc for task in final_response["tasks"] for doc in task.get("structured_query", {}).get("documents", [])]
#final_response["used_documents"] = list(set(doc_used))
#
#self.CFG.storage.write(user_id, final_response)
#
#file_name = str(final_response["id"]).replace(":", "_").replace(".", "_")
#
#write_file(
#    os.path.join(self.CFG.project_root, "documents", "result", f"{file_name}.json"), 
#    final_response
#)
#
#return final_response["result"]