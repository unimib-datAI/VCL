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

CFG = Config.get_instance()

rewriting = Rewriting(CFG)
planner = Planner(CFG)
retrieval = Retrieval(CFG)
generator = Generator(CFG)

logger = CFG.logger


# Define the request body structure for the /chat endpoint
class ChatInput(BaseModel):
    message: str  # User's input message
    thread_id: str  # Conversation identifier


# POST endpoint for handling chat messages
@app.post("/chat")
async def chat(request: ChatInput):
    timestamp = datetime.now(timezone.utc)

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

    # Step 3: Retrieval + Generation per op
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
                    "result_preview": text[:200],  # evita log enormi
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

    # Step 4: Cleanup
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
