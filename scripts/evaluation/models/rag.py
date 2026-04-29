"""Evaluation adapter for a local FAISS retrieval-augmented generation baseline."""

import json
import faiss
import numpy as np
import tiktoken
from typing import List, Dict
from openai import OpenAI
import voyageai

# --- Retrieval configuration ---
EMBED_MODEL = "text-embedding-3-large"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128
RETRIEVE_K = 64
FINAL_K = 10
MAX_CONTEXT_TOKENS = 20000 
EMBED_BATCH_SIZE = 64
RERANK_MODEL = "rerank-2.5"

client = OpenAI()
vo_client = voyageai.Client()
tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping token chunks for vector indexing.
    """
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

'''def embed_texts(texts: List[str], input_type: str = "document") -> np.ndarray:
    """
    Generate embeddings with Voyage AI.

    input_type can be "document" or "query".
    """
    # Voyage handles batches internally, but explicit batching can still help
    # when the corpus is large or rate limits are tight.
    
    resp = vo_client.embed(
        texts=texts,
        model=EMBED_MODEL,
        input_type=input_type
    )
    
    vectors = np.array(resp.embeddings, dtype=np.float32)
    
    # Normalizzazione per la ricerca vettoriale (Inner Product)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors'''

def embed_texts(texts: List[str], input_type = None) -> np.ndarray:
    """
    Generate normalized OpenAI embeddings for a list of texts.
    """
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

def rerank_and_trim(docs: List[Dict], max_tokens: int = MAX_CONTEXT_TOKENS):
    """
    Sort retrieved chunks by score and keep as much context as the token budget allows.
    """
    docs = sorted(docs, key=lambda d: d.get("score", 0), reverse=True)
    
    selected_chunks = []
    used_sources = set()
    
    current_tokens = 0
    separator = "\n\n---\n\n"
    separator_tokens = len(tokenizer.encode(separator))

    for d in docs:
        chunk_tokens = len(tokenizer.encode(d["content"]))
        additional_cost = chunk_tokens + (separator_tokens if selected_chunks else 0)

        if current_tokens + additional_cost <= max_tokens:
            selected_chunks.append(d["content"])
            
            if "source" in d:
                used_sources.add(d["source"])
                
            current_tokens += additional_cost
        else:
            break 

    return separator.join(selected_chunks), list(used_sources)

class RagIndex:
    """Thin FAISS index wrapper for chunk retrieval."""

    def __init__(self, vectors: np.ndarray, docs: List[Dict]):
        """Build an inner-product FAISS index from normalized vectors."""
        self.docs = docs
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

    def retrieve(self, query: str, k: int) -> List[Dict]:
        """Retrieve the top-k chunks that are closest to the query."""
        # Use query-style embeddings for search input.
        q_emb = embed_texts([query], input_type="query")
        scores, indices = self.index.search(q_emb, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(self.docs):
                doc = self.docs[idx].copy()
                doc["score"] = float(score)
                results.append(doc)
        return results

class RAGModel:
    """RAG baseline that retrieves chunks and asks an OpenAI chat model."""

    def __init__(self, model: str):
        """Store model configuration and delay index creation."""
        self.index = None
        self.model = model
    
    @property
    def name(self):
        """Return the display name used in evaluation outputs."""
        return f"RAG with {self.model}"

    def voyage_rerank(self, query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
        """Rerank retrieved chunks using the Voyage AI cross-encoder."""
        if not docs:
            return []

        documents_content = [d["content"] for d in docs]
        reranking_resp = vo_client.rerank(
            query=query,
            documents=documents_content,
            model=RERANK_MODEL, 
            top_k=top_k,
            truncation=True
        )

        reranked_results = []
        for result in reranking_resp.results:
            original_doc = docs[result.index].copy()
            original_doc["score"] = result.relevance_score
            reranked_results.append(original_doc)

        return reranked_results

    def initialize(self, paths: List[str]):
        """
        Build the retrieval index from the provided document paths.
        """
        return
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
            # Use document-style embeddings for index creation.
            vectors = embed_texts(all_chunks, input_type="document")
            self.index = RagIndex(vectors, all_docs)

    def query(self, question: str):
        """
        Retrieve context and generate an answer with the configured chat model.
        """
        return
        if self.index is None:
            raise RuntimeError("Devi inizializzare l'indice caricando i documenti prima di fare una query.")

        # 1. Retrieval.
        initial_docs = self.index.retrieve(question, RETRIEVE_K)

        # 2. Rerank.
        reranked_docs = self.voyage_rerank(question, initial_docs, top_k=RETRIEVE_K)

        # 3. Context and source tracking.
        context_text, used_sources = rerank_and_trim(reranked_docs, max_tokens=MAX_CONTEXT_TOKENS)

        if not context_text:
            return {"content": "Non ho trovato informazioni sufficienti.", "sources": []}

        # 4. Chat completion.
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system", 
                    "content": "Sei un assistente legale preciso. Rispondi SOLO usando il contesto fornito."
                },
                {
                    "role": "user", 
                    "content": f"Contesto:\n{context_text}\n\nDomanda:\n{question}"
                }
            ],
            temperature=0.0
        )
        
        return {
            "content": response.choices[0].message.content.strip(),
            "sources": used_sources
        }
