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
from fastapi import FastAPI
from pydantic import BaseModel

from utils.config import Config
from utils.file_manager import write_file

from decomposer import Decomposer
from rewriting import Rewriting
from retrieval import Retrieval
from generator import Generator

# Create the FastAPI application instance
app = FastAPI()

# Load the global configuration
CFG = Config.get_instance()

# Initialize components
decomposer = Decomposer.get_instance(CFG)
rewriting = Rewriting.get_instance(CFG)
retrieval = Retrieval.get_instance(CFG)
generator = Generator.get_instance(CFG)

logger = CFG.get_logger("Main")

class ChatInput(BaseModel):
    """
    Schema for the /chat POST request body.

    Attributes:
        query (str): The user's input message to be processed.
        user_id (str): Unique identifier for the conversation thread.
    """

    query: str
    user_id: str

@app.post("/chat")
async def chat(request: ChatInput):
    """
    Process a chat message through the DQL system.

    Steps:
    1. Log the incoming request.
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
    logger.info(f"Request Received: \"{request.query}\"")
    
    # Save id request
    timestamp = str(datetime.now(timezone.utc).isoformat())
    request_id = f"{str(request.user_id)}_{timestamp}"

    # Step 1: Decompose
    logger.info("Step 1 (Decompose): Starting")
    query_graph = decomposer.decompose(request.query)
    logger.info("Step 1 (Decompose): Done")
    
    i = 1
    for node in nx.topological_sort(query_graph):
        node_data = query_graph.nodes[node]["data"]
        
        node_data["order"] = i
        
        logger.info(f"Starting subtask {str(i)}/{str(query_graph.number_of_nodes())}: \"{node_data["prompt"]}\"")
        
        # Step 2: Rewriting
        logger.info("Step 2 (Rewriting): Starting")
        node_data["structured_query"] = rewriting.rewrite(node_data, request.user_id)
        logger.info("Step 2 (Rewriting): Done")
        
        # Step 3: Retrieval
        logger.info("Step 3 (Retrieval): Starting")
        doc = retrieval.execute(node_data["structured_query"], request.user_id)
        logger.info("Step 3 (Retrieval): Done")
        
        # Step 4: Generation
        logger.info("Step 4 (Generation): Starting")
        node_data["result"] = generator.generate(node_data["structured_query"], doc, node_data["prompt"])
        logger.info("Step 4 (Generation): Done")
        
        query_graph.nodes[node]["data"].update(node_data)
        
        i += 1
        
    final_response = {
        "id": request_id,
        "input": request.query,
        "tasks": [query_graph.nodes[node]["data"] for node in nx.topological_sort(query_graph)],
        "result": query_graph.nodes[list(nx.topological_sort(query_graph))[-1]]["data"]["result"]
    }
    
    CFG.storage.write(request.user_id, final_response)
    
    file_name = str(final_response["id"]).replace(":", "_").replace(".", "_")
    
    write_file(
        os.path.join(CFG.project_root, "documents", "result", f"{file_name}.json"), 
        final_response
    )
    
    return final_response
    