# config.py
import os
import json

class Config:
    def __init__(self, api_key_path: str = "api_key.txt", docs_path: str = "documents"):
        self.GOOGLE_API_KEY = self._load_api_key(api_key_path)
        os.environ["GOOGLE_API_KEY"] = self.GOOGLE_API_KEY
        
        self.docs_path = docs_path
        
        self.command_map = {
            "a": "cerca", 
            "b": "riassumi", 
            "c": "confronta",
            "d": "estrai", 
            "e": "esplora", 
            "f": "espandi",
            "g": "verifica", 
            "h": "integra", 
            "i": "valutaRil",
            "l": "calcola", 
            "m": "altro"
        }
        
        self.command_descriptions = {
            "cerca": "Cerca porzioni del documento che contengano le informazioni richieste e fornisce una risposta completa utilizzando direttamente tali contenuti, senza riformularli.",
            "riassumi": "Riassume il contenuto in modo chiaro e conciso, mantenendo i punti chiave entro un limite prefissato di parole.",
            "confronta": "Confronta due documenti per evidenziare similitudini e differenze a livello strutturale, semantico o argomentativo.",
            "estrai": "Analizza il documento per estrarre componenti logiche implicite (es. struttura semantica, sillogismi, percorso argomentativo non esplicito). A differenza di 'A' le informazioni possono essere riformulate.",
            "esplora": "Identifica e raggruppa tutte le citazioni o riferimenti a un tema specifico presenti nel documento.",
            "espandi": "Espande un testo fino a un certo numero di parole, aggiungendo esempi, spiegazioni e dettagli in modo coerente.",
            "verifica": "Verifica la coerenza tra le motivazioni e le decisioni finali presenti nel documento, segnalando eventuali incongruenze.",
            "integra": "Genera un nuovo testo coerente unificando logicamente più estratti o documenti, evitando ridondanze.",
            "valutaRil": "Valuta la rilevanza di un argomento/documento/precedente giuridico rispetto alla decisione finale, motivando il giudizio.",
            "calcola": "Esegue calcoli basati su dati numerici presenti nel testo.",
            "altro": ""
        }

    def _load_api_key(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read().strip()

    def load_documents(self) -> list[dict]:
        docs = []
        for fn in os.listdir(self.docs_path):
            with open(os.path.join(self.docs_path, fn), "r") as f:
                docs.append(json.load(f))
        return docs
