'''import json
import faiss
import numpy as np
import tiktoken
from typing import List, Dict
from openai import OpenAI
import voyageai

# --- Configurazione ---
# --- Nuova Configurazione ---
EMBED_MODEL = "text-embedding-3-large"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128
RETRIEVE_K = 64
FINAL_K = 10
MAX_CONTEXT_TOKENS = 20000 
EMBED_BATCH_SIZE = 64
RERANK_MODEL = "rerank-multilingual-v3.0"

client = OpenAI()
vo_client = voyageai.Client()
tokenizer = tiktoken.get_encoding("cl100k_base")

# --- Funzioni di Utility ---
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
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

def embed_texts(texts: List[str], input_type: str = "document") -> np.ndarray:
    """
    Usa Voyage AI per generare embedding.
    input_type può essere "document" o "query".
    """
    # Voyage gestisce i batch internamente, ma per sicurezza o limiti di rate
    # possiamo mantenere una logica di batching se i testi sono migliaia.
    
    resp = vo_client.embed(
        texts=texts,
        model=EMBED_MODEL,
        input_type=input_type
    )
    
    vectors = np.array(resp.embeddings, dtype=np.float32)
    
    # Normalizzazione per la ricerca vettoriale (Inner Product)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors

def rerank_and_trim(docs: List[Dict], max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    # Ordina i documenti per score decrescente (Cross-Encoder score)
    docs = sorted(docs, key=lambda d: d.get("score", 0), reverse=True)
    
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
            break # Smettiamo di aggiungere se superiamo il limite

    return separator.join(selected_chunks)

# --- Classi Principali ---
class RagIndex:
    def __init__(self, vectors: np.ndarray, docs: List[Dict]):
        self.docs = docs
        self.dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(vectors)

    def retrieve(self, query: str, k: int) -> List[Dict]:
        # IMPORTANTE: Usiamo input_type="query" qui
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
    def __init__(self, model: str):
        self.index = None
        self.model = model
    
    @property
    def name(self):
        return f"RAG with {self.model}!"

    def voyage_rerank(self, query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
        """Esegue il reranking usando il Cross-Encoder di Voyage AI."""
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
            # Usiamo input_type="document" per l'indicizzazione
            vectors = embed_texts(all_chunks, input_type="document")
            self.index = RagIndex(vectors, all_docs)

    def query(self, question: str) -> str:
        if self.index is None:
            raise RuntimeError("Devi inizializzare l'indice caricando i documenti prima di fare una query.")

        # 1. Retrieval iniziale (Vettoriale)
        initial_docs = self.index.retrieve(question, RETRIEVE_K)

        # 2. Reranking (Cross-Encoder)
        reranked_docs = self.voyage_rerank(question, initial_docs, top_k=RETRIEVE_K)

        # 3. Preparazione del contesto e trimming
        # Usiamo il limite globale MAX_CONTEXT_TOKENS
        context_text = rerank_and_trim(reranked_docs, max_tokens=MAX_CONTEXT_TOKENS)

        if not context_text:
            return "Non ho trovato informazioni sufficienti nei documenti per rispondere."

        # 4. Chat Completion
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system", 
                    "content": "Sei un assistente legale preciso. Rispondi SOLO usando il contesto fornito. Se non trovi la risposta, dillo chiaramente."
                },
                {
                    "role": "user", 
                    "content": f"Contesto:\n{context_text}\n\nDomanda:\n{question}"
                }
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()'''