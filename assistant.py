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

from utils.config import Config
from utils.file_manager import write_file

from decomposer import Decomposer
from bot.translator.rewriting import Rewriting
from retrieval import Retrieval
from generator import Generator

class Assistant():
    # Load the global configuration
    CFG = Config.get_instance()

    # Initialize components
    decomposer = Decomposer.get_instance(CFG)
    rewriting = Rewriting.get_instance(CFG)
    retrieval = Retrieval.get_instance(CFG)
    generator = Generator.get_instance(CFG)

    logger = CFG.get_logger("Main")

    def chat(self, query: str, user_id: str):
        """
        Process a chat message through the DQL system.

        Steps:
        1. Log the incoming 
        2. Rewrite the input message.
        3. Decompose the rewritten query into operations.
        4. For each operation:
        a. Retrieve relevant documents.
        b. Generate a textual response.
        c. Store the results.
        5. Clear intermediate storage and return the final result.

        Args:
            request (ChatInput): The incoming chat request containing
                the message and user_id.

        Returns:
            dict: The final result of the chat operation, including the
                generated text and metadata.
        """
        # Log start of chat processing
        self.logger.info(f"Request Received: \"{query}\"")
        
        # Save id request
        timestamp = str(datetime.now(timezone.utc).isoformat())
        request_id = f"{str(user_id)}_{timestamp}"

        # Step 1: Decompose
        self.logger.info("Step 1 (Decompose): Starting")
        query_graph = self.decomposer.decompose(query)
        self.logger.info("Step 1 (Decompose): Done")
        
        i = 1
        for node in nx.topological_sort(query_graph):
            node_data = query_graph.nodes[node]["data"]
            
            node_data["order"] = i
            
            self.logger.info(f"Starting subtask {str(i)}/{str(query_graph.number_of_nodes())}: \"{node_data["prompt"]}\"")
            
            # Step 2: Rewriting
            self.logger.info("Step 2 (Rewriting): Starting")
            node_data["structured_query"] = self.rewriting.rewrite(node_data, user_id)
            self.logger.info("Step 2 (Rewriting): Done")
            
            # Step 3: Retrieval
            self.logger.info("Step 3 (Retrieval): Starting")
            doc = self.retrieval.execute(node_data["structured_query"], query_graph, user_id)
            self.logger.info("Step 3 (Retrieval): Done")
            
            # Step 4: Generation
            self.logger.info("Step 4 (Generation): Starting")
            node_data["result"], node_data["structured_query"] = self.generator.generate(node_data["structured_query"], doc, node_data["prompt"])
            self.logger.info("Step 4 (Generation): Done")
            
            query_graph.nodes[node]["data"].update(node_data)
            
            i += 1
            
        final_response = {
            "id": request_id,
            "input": query,
            "tasks": [query_graph.nodes[node]["data"] for node in nx.topological_sort(query_graph)],
            "result": query_graph.nodes[list(nx.topological_sort(query_graph))[-1]]["data"].get("result", "")
        }
        
        doc_used = [doc for task in final_response["tasks"] for doc in task.get("structured_query", {}).get("documents", [])]
        final_response["used_documents"] = list(set(doc_used))
        
        self.CFG.storage.write(user_id, final_response)
        
        file_name = str(final_response["id"]).replace(":", "_").replace(".", "_")
        
        write_file(
            os.path.join(self.CFG.project_root, "documents", "result", f"{file_name}.json"), 
            final_response
        )
        
        return final_response["result"]
    
    def __init__(self):
        pass
    