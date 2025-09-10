"""
This module defines a FastAPI application for the DQL system.

It provides an endpoint (/chat) for processing chat messages, which involves:
1. Rewriting the input query using the Rewriting module.
2. Decomposing the rewritten query into operations via the Planner.
3. Retrieving relevant documents and generating answers for each operation.
4. Logging all steps and storing intermediate and final results.
"""

import json
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel

from utils.config import Config
from rewriting import Rewriting
from planner import Planner
from retrieval import Retrieval
from generator import Generator

# Create the FastAPI application instance
app = FastAPI()

# Load the global configuration
CFG = Config.get_instance()

# Initialize components
rewriting = Rewriting(CFG)
planner = Planner(CFG)
retrieval = Retrieval(CFG)
generator = Generator(CFG)

logger = CFG.logger


class ChatInput(BaseModel):
    """
    Schema for the /chat POST request body.

    Attributes:
        message (str): The user's input message to be processed.
        thread_id (str): Unique identifier for the conversation thread.
    """

    message: str
    thread_id: str


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
            the message and thread_id.

    Returns:
        dict: The final result of the chat operation, including the
            generated text and metadata.
    """
    timestamp = datetime.now(timezone.utc)

    # Log start of chat processing
    logger.info(
        json.dumps(
            {
                "step": "API.chat",
                "action": "start",
                "thread_id": request.thread_id,
                "message": request.message,
                "timestamp": timestamp.isoformat(),
            }
        )
    )

    # Step 1: Rewriting
    dql = rewriting.rewrite(request.message, request.thread_id)
    logger.info(
        json.dumps(
            {"step": "API.chat", "action": "rewriting_done", "rewriting_result": dql}
        )
    )

    # Step 2: Planning
    ops = planner.decompose(dql)
    logger.info(
        json.dumps(
            {
                "step": "API.chat",
                "action": "planning_done",
                "num_operations": len(ops),
                "operations": ops,
            }
        )
    )

    # Step 3: Retrieval + Generation per operation
    for op in ops:
        logger.info(
            json.dumps(
                {
                    "step": "API.chat",
                    "action": "operation_start",
                    "operation_id": op["id"],
                    "operation_command": op["command"],
                }
            )
        )

        doc = retrieval.execute(op, request.thread_id)
        logger.info(
            json.dumps(
                {
                    "step": "API.chat",
                    "action": "retrieval_done",
                    "operation_id": op["id"],
                    "num_docs": len(doc),
                }
            )
        )

        text = generator.generate(op, doc, dql["query"])
        logger.info(
            json.dumps(
                {
                    "step": "API.chat",
                    "action": "generation_done",
                    "operation_id": op["id"],
                    "result_preview": text[:200],
                }
            )
        )

        file = {
            "time": timestamp.isoformat(),
            "name": op["id"],
            "dql": op,
            "documents": op["documents"],
            "text": text,
        }

        CFG.storage.write(request.thread_id, file)
        logger.info(
            json.dumps(
                {
                    "step": "API.chat",
                    "action": "storage_write",
                    "operation_id": op["id"],
                }
            )
        )

    # Step 4: Cleanup DB
    CFG.storage.clear(request.thread_id)
    logger.info(
        json.dumps(
            {
                "step": "API.chat",
                "action": "storage_cleared",
                "thread_id": request.thread_id,
            }
        )
    )

    # Step 5: Return final result
    result = CFG.storage.get_last_element(request.thread_id)
    logger.info(
        json.dumps(
            {
                "step": "API.chat",
                "action": "end",
                "final_result_preview": result.get("text", "")[:200],
                "thread_id": request.thread_id,
            }
        )
    )

    return result
