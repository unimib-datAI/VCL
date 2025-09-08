# dql
Description Query Language

## How to Run the Code

To run this project, follow these steps:

1. Install dependencies
```bash
pip install -r requirements.txt
```
2. Go to the [Gemini API website](https://aistudio.google.com/app/apikey)
3. Generate a new API key.
4. Copy the generated key and paste it into a file named `api_key.txt`. Optionally, you can run `main.py` with the `-api` flag if you want to store the key.
5. Insert an upstash-redis URL and token into the `url_redis.txt` and `token_redis.txt` files in the settings directory (create the files if necessary)
6. Make sure you are connected to your university's VPN — this is required to access the Elasticsearch database.
7. Run the `main.py` file. Use the `-rag` flag if you want only relevant chunks to be used during retrieval.
```bash
python main.py
```
8. Make a request to `http://127.0.0.1:8000/chat` with the following additional parameters:
- `message`: the query to execute
- `thread_id`: unique user ID

## System
![image](images/system.png)

## Rewriting System

![image](images/graph.png)
