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
def initial_state(query: str):
    return {
        "query": query,      # Original user query
        "command": "",       # Placeholder for a command
        "where": [],         # Placeholder for conditions/filters
        "what": {},          # Placeholder for requested information
        "ent": {},           # Placeholder for recognized entities
        "phr": {},           # Placeholder for recognized phrases
        "how": {},           # Placeholder for processing instructions
        "iteration": 0,      # Counter for processing iterations
        "feedback": "",      # Placeholder for feedback
        "response": {}       # Placeholder for the generated response
    }

# POST endpoint for handling chat messages
@app.post("/chat")
async def chat(input: ChatInput):
    # Configuration containing the conversation ID
    config = {"configurable": {"thread_id": input.thread_id}}

    # Asynchronously invoke the graph processing function with the initial state and configuration
    response = await graph.ainvoke(initial_state(input.message), config=config)

    # Return the DQL-structured query from the response
    return response["response"].content
