"""FastAPI entry point that exposes the DQL orchestration pipeline."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from utils.config import Config
from api.dqlEngine.orchestrator.orchestrator import Orchestrator 

class ChatRequest(BaseModel):
    """Request payload accepted by the chat endpoint."""

    prompt: str
    user_id: str
    chat_id: str
    request_id: Optional[str] = None
    source_id: Optional[str] = None

app = FastAPI(title="DQL Orchestrator API", root_path="/api")

# Create shared services once at import time so requests reuse the same pipeline.
cfg = Config.get_instance()
orchestrator = Orchestrator(cfg)

@app.post("/answer")
def chat_endpoint(request: ChatRequest):
    """Run a user prompt through the DQL orchestrator and return the answer."""
    try:
        # Default to the shared "vitali" corpus when the client sends no source.
        request.source_id = (request.source_id or "").strip() or "vitali"

        # Convert the Pydantic model to the plain dict shape expected downstream.
        return orchestrator.answer(dict(request))
    except Exception as e:
        # Hide stack traces from the client while preserving the error message.
        raise HTTPException(
            status_code=500, 
            detail=f"Errore interno del server durante l'elaborazione: {str(e)}"
        )
        
