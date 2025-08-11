from fastapi import FastAPI
from graph import graph
from pydantic import BaseModel

app = FastAPI()

class ChatInput(BaseModel):
    message: str
    thread_id: str

def initial_state(query: str):
    return {
        "query": query,
        "command": "",
        "where": [],
        "what": {},
        "ent": {},
        "phr": {},
        "how": {},
        "iteration": 0,
        "feedback": "",
        "response": {}
    }

@app.post("/chat")
async def chat(input: ChatInput):
    config = {"configurable": {"thread_id": input.thread_id}}
    response = await graph.ainvoke(initial_state(input.message), config=config)
    return response["messages"][-1].content