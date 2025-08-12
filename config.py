from langchain.chat_models import init_chat_model
import os
import ast
import json
import argparse


class Config:
    # ElasticSearch database URL
    DB_URL = 'http://10.0.0.108:9201'

    # LLM model and provider
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"

    # Default behavior for RAG: extract full documents
    rag: bool = False

    # URL and headers for the rewriting system
    url = "http://127.0.0.1:8000/chat"
    headers = {"Content-Type": "application/json"}

    # Mapping of single-letter keys to internal command names
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

    # Descriptions for each available command
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

    def __init__(self, opts: argparse.Namespace = None):
        api_key = None

        # Load options from CLI arguments if provided
        if opts:
            api_key = opts.api_key
            self.rag = opts.rag
            self.seconds = opts.seconds  # Presumably used elsewhere in the program

        # Path where the API key is stored
        api_path = os.path.join('settings', 'api_key.txt')

        # If no API key was passed, try reading from the file
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = self.read_file(api_path)

        # Set the environment variable for the Google GenAI API
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            
            # Save the key again (could be useful if normalized or updated)
            self.write_file(api_path, api_key)
        else:
            raise ValueError('No API key could be found.')
            

        # Initialize the LLM model from LangChain
        self.llm = init_chat_model(self.model_name, model_provider=self.provider)

    def get_command_from_key(self, key: str) -> str:
        """
        Given a single-character key, return the associated command name.
        Defaults to 'altro' if not found.
        """
        return self.command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        """
        Given either a command key (single letter) or a command name,
        return the human-readable description.
        """
        if len(key) == 1:  # If single letter, convert to command name
            key = self.get_command_from_key(key)
        
        return self.command_descriptions.get(key, "")

    @staticmethod
    def read_file(path: str) -> str:
        """Read a text file and return its stripped content."""
        with open(path, "r") as f:
            return f.read().strip()

    @staticmethod
    def write_file(path: str, key: str):
        """Write the given string to a file, creating directories if needed."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(key)

    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Extract the first JSON object found in a string and parse it into a dictionary.
        """
        output = output[output.index("{"): output.rfind("}") + 1]
        return json.loads(output)

    @staticmethod
    def str_in_list(output: str) -> list:
        """
        Extract the first list structure from a string and parse it
        """
        output = output[output.index("["): output.rfind("]") + 1]
        return ast.literal_eval(output)
