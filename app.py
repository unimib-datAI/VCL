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
planner = Planner()
retrieval = Retrieval(CFG)
generator = Generator(CFG)


# Define the request body structure for the /chat endpoint
class ChatInput(BaseModel):
    message: str  # User's input message
    thread_id: str  # Conversation identifier


# POST endpoint for handling chat messages
@app.post("/chat")
async def chat(request: ChatInput):
    timestamp = datetime.now(timezone.utc)

    dql = rewriting.rewrite(request.message, request.thread_id)
    ops = planner.decompose(dql)

    for op in ops:
        doc = retrieval.execute(op, request.thread_id)
        text = generator.generate(op, doc, dql["query"])

        file = {
            "time": timestamp.isoformat(),
            "name": op["id"],
            "dql": op,
            "documents": op["documents"],
            "text": text,
        }

        CFG.storage.write(request.thread_id, file)

    CFG.storage.clear(request.thread_id)

    return CFG.storage.get_last_element(request.thread_id)
