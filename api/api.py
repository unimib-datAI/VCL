import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# Assumiamo l'import della tua pipeline
from utils.config import Config
from api.dqlEngine.orchestrator.orchestrator import Orchestrator 

class ChatRequest(BaseModel):
    prompt: str
    user_id: str
    chat_id: str
    request_id: Optional[str] = None
    source_id: Optional[str] = None

app = FastAPI(title="DQL Orchestrator API", root_path="/api")

cfg = Config.get_instance()
orchestrator = Orchestrator(cfg)

@app.post("/answer")
def chat_endpoint(request: ChatRequest):
    try:
        request.source_id = (request.source_id or "").strip() or "vitali"
        return orchestrator.answer(dict(request))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Errore interno del server durante l'elaborazione: {str(e)}"
        )
        