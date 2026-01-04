import json
import faiss
import numpy as np
import tiktoken
from typing import List, Dict
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

RETRIEVE_K = 25
FINAL_K = 5
MAX_CONTEXT_TOKENS = 20000 

EMBED_BATCH_SIZE = 64

client = OpenAI()
tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(text: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    tokens = tokenizer.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(tokenizer.decode(chunk_tokens))
        if end >= len(tokens):
            break
        start = end - overlap

    return chunks

def embed_texts(texts: List[str]) -> np.ndarray:
    vectors_all = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(
            model=EMBED_MODEL,
            input=batch
        )
        vectors = np.array(
            [e.embedding for e in resp.data],
            dtype=np.float32
        )
        
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors_all.append(vectors)

    return np.vstack(vectors_all)

class RagIndex:
    def __init__(self, vectors: np.ndarray, docs: List[Dict]):
        self.docs = docs
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

    def retrieve(self, query: str, k: int) -> List[Dict]:
        q_emb = embed_texts([query])
        scores, indices = self.index.search(q_emb, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(self.docs):
                doc = self.docs[idx].copy()
                doc["score"] = float(score)
                results.append(doc)
        return results

def rerank_and_trim(docs: List[Dict],
                    max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    docs = sorted(docs, key=lambda d: d["score"], reverse=True)
    
    selected_chunks = []
    current_tokens = 0
    
    separator = "\n\n---\n\n"
    separator_tokens = len(tokenizer.encode(separator))

    for d in docs:
        chunk_tokens = len(tokenizer.encode(d["content"]))
    
        costo_aggiuntivo = chunk_tokens + (separator_tokens if selected_chunks else 0)

        if current_tokens + costo_aggiuntivo <= max_tokens:
            selected_chunks.append(d["content"])
            current_tokens += costo_aggiuntivo
        else:
            continue 

    return separator.join(selected_chunks)

class RAGModel:
    def __init__(self, model):
        self.index = None
        self.model = model
    
    @property
    def name(self):
        return f"RAG with {self.model}"

    def initialize(self, paths: List[str]):
        all_docs = []
        all_chunks = []

        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                text_content = data.get("text", "")

            chunks = chunk_text(text_content)

            for i, chunk in enumerate(chunks):
                all_docs.append({
                    "content": chunk,
                    "source": path,
                    "chunk_id": i
                })
                all_chunks.append(chunk)

        if all_chunks:
            vectors = embed_texts(all_chunks)
            self.index = RagIndex(vectors, all_docs)

    def query(self, question: str) -> str:
        if self.index is None:
            raise RuntimeError("You must upload your documents before.")

        # 1. Retrieval
        retrieved = self.index.retrieve(question, RETRIEVE_K)

        # 2. Context preparation
        context = rerank_and_trim(retrieved)

        # 3. Chat Completion
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system", 
                    "content": "Rispondi SOLO usando il contesto fornito."
                },
                {
                    "role": "user", 
                    "content": f"Contesto:\n{context}\n\nDomanda:\n{question}"
                }
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()