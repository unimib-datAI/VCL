from fastapi import FastAPI
from graph import graph
from pydantic import BaseModel

# Create the FastAPI application instance
app = FastAPI()

# Define the request body structure for the /chat endpoint
class ChatInput(BaseModel):
    message: str    # User's input message
    thread_id: str  # Conversation identifier

# Build the initial state object for processing
def initial_state(query: str, thread_id: str):
    return {
        "query": query,      # Original user query
        "thread_id": thread_id,
        "command": "",
        "description_command": "",
        "documents": [],
        "id_result": "",
        "unit": "",
        "what_name": "",
        "what_type": "",
        "what_description": "",
        "how_section": "",
        "how_data": "",
        "how_response": "",
        "iteration": 0,
        "feedback": "",
        "response": {}
    }

# POST endpoint for handling chat messages
@app.post("/chat")
async def chat(input: ChatInput):
    # Configuration containing the conversation ID
    config = {"configurable": {"thread_id": input.thread_id}}

    # Asynchronously invoke the graph processing function with the initial state and configuration
    response = await graph.ainvoke(initial_state(input.message, input.thread_id), config=config)

    # Return the DQL-structured query from the response
    return response["response"]
