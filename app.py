from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone

from utils.config import Config
from rewriting import Rewriting
from planner import Planner
from retrieval import Retrieval
from generator import Generator

# Create the FastAPI application instance
app = FastAPI()

cfg = Config.get_instance()

rewriting = Rewriting(cfg)
planner = Planner(cfg)
retrieval = Retrieval(cfg)
generator = Generator(cfg)

# Define the request body structure for the /chat endpoint
class ChatInput(BaseModel):
    message: str    # User's input message
    thread_id: str  # Conversation identifier

# POST endpoint for handling chat messages
@app.post("/chat")
async def chat(input: ChatInput):
    timestamp = datetime.now(timezone.utc)
            
    dql = rewriting.rewrite(input.message, input.thread_id)
    ops = planner.decompose(dql)
    
    for op in ops:
        doc = retrieval.execute(op, input.thread_id)
        text = generator.generate(op, doc, dql["query"])
        
        file = {
            "time": timestamp.isoformat(),
            "name": op["id"],
            "dql": op,
            "documents": op["documents"],
            "text": text
        }
        
        cfg.storage.write(input.thread_id, file)
        
    cfg.storage.clear(input.thread_id)
    
    return cfg.storage.get_last_element(input.thread_id)
    
