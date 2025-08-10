from langchain.chat_models import init_chat_model

import os
import json
import argparse

class Config:
    DB_URL = 'http://10.0.0.108:9201'
    
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"    
    llm = init_chat_model(model_name, model_provider=provider)
    
    command_map = {
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
    
    command_descriptions = {
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
        
    def __init__(self, opts: argparse.Namespace):
        
        """
            Step 1: Setting API key
            
            An API key can be specified on the command line or the last used key can be retrieved.
        """
        
        api_key = opts.api_key
        api_path = os.path.join('settings', 'api_key.txt')
        
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = self.read_file(api_path)
                
        if not api_key:
            raise ValueError('No API key could be found.')
        else:
            self.write_file(api_path, api_key)
                    
        os.environ["GOOGLE_API_KEY"] = api_key
        
        """
            Step 2: Setting Retrieval
            
            It is stored whether the entire document (False) or only the relevant chunks (True) should be retrieved during retrieval.
        """
        
        self.rag = opts.rag

    @staticmethod
    def read_file(path: str) -> str:
        with open(path, "r") as f:
            return f.read().strip()
    
    @staticmethod
    def write_file(path: str, key: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w") as f:
            f.write(key)
    
    @staticmethod
    def str_in_dict(output: str) -> dict:
        output = output[output.index("{") : output.rfind("}") + 1]
        return json.loads(output)

    @staticmethod
    def str_in_list(output: str) -> list:
        output = output[output.index("[") : output.rfind("]") + 1]
        return eval(output)

    @staticmethod
    def get_command_from_key(self, key: str) -> str:
        return self.command_map.get(key, "altro")
    
    @staticmethod
    def get_description_from_command(self, key: str) -> str:
        if len(key) == 1:
            key = self.get_command_from_key(self, key)
        
        return self.command_descriptions.get(key, "")
