from openai import OpenAI

client = OpenAI()

class GPTModel():
    def __init__(self, model):
        self.vector_store_id = None
        self.model = model
        self.file_paths = []

    @property
    def name(self):
        return f"{self.model} + FileSearch"

    def initialize(self, paths):
        self.file_paths = paths

        vector_store = client.vector_stores.create(name="MyFileStore")
        self.vector_store_id = vector_store.id

        for path in self.file_paths:
            with open(path, "rb") as f:
                client.vector_stores.files.upload_and_poll(
                    vector_store_id=self.vector_store_id,
                    file=f
                )

    def query(self, question: str):
        if not self.vector_store_id:
            raise ValueError("You must execute initialize() before.")

        response = client.responses.create(
            model=self.model,
            input=question,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id]
                }
            ],
            include=["file_search_call.results"]
        )

        content = ""
        if hasattr(response, 'output_text'):
            content = response.output_text
        
        return {
            "content": content,
            "info": dict(response)
        }
