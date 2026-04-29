"""Evaluation adapter for OpenAI File Search."""

import re

from openai import OpenAI

client = OpenAI()

class GPTModel():
    """Wrap OpenAI File Search so it matches the evaluation model interface."""

    def __init__(self, model):
        """Store model settings and delayed vector store state."""
        self.vector_store_id = None
        self.model = model
        self.file_paths = []

    @property
    def name(self):
        """Return the display name used in evaluation outputs."""
        return f"{self.model} + FileSearch"
    
    def extract_sources(self, info):
        """
        Extract cited filenames from the raw OpenAI response metadata.
        """
        pattern = r"filename='([^']*)'"
        
        try:
            info_string = str("\n".join(info["info"]["output"]))
        except Exception:
            info_string = str(info)
            
        used_doc = sorted([f for f in set(re.findall(pattern, info_string))])
        return { "sources": used_doc }

    def initialize(self, paths):
        """
        Upload documents to a vector store before querying.
        """
        return
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
        """
        Ask the configured OpenAI model with File Search enabled.
        """
        return
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
        
        result = { "content": content }
        result.update(self.extract_sources(dict(response)))
        
        return result
