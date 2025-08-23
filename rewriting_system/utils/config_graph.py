import ast
import json
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from utils.LLM import LLM

class Config:
    """
    System configuration class.
    Implemented as a singleton to ensure only one global instance.
    """

    # Class variable that will contain the single instance
    _instance = None

    # Maximum number of iterations of the rewriting system
    max_iteration: int = 3

    # Default value for GEMINI API KEY
    api_key = None
    
    # Default value for SECONDS: time we must wait after all LLM calls
    seconds: int = 0

    # Mapping of single-letter keys to internal command names
    command_map = {
        "a": "cerca",
        "b": "riassumi",
        "c": "confronta",
        "d": "estrai",
        "e": "esplora",
        "f": "espandi",
        "g": "calcola",
        "h": "altro"
    }

    # Descriptions for each available command
    command_descriptions = {
        "cerca": "Cerca porzioni del documento che contengano le informazioni richieste e fornisce una risposta completa utilizzando direttamente tali contenuti, senza riformularli.",
        "riassumi": "Riassume il contenuto in modo chiaro e conciso, mantenendo i punti chiave entro un limite prefissato di parole.",
        "confronta": "Confronta due documenti per evidenziare similitudini e differenze a livello strutturale, semantico o argomentativo.",
        "estrai": "Analizza il documento per estrarre componenti logiche implicite (es. struttura semantica, sillogismi, percorso argomentativo non esplicito). A differenza di 'A' le informazioni possono essere riformulate.",
        "esplora": "Identifica e raggruppa tutte le citazioni o riferimenti a un tema specifico presenti nel documento.",
        "espandi": "Espande un testo fino a un certo numero di parole, aggiungendo esempi, spiegazioni e dettagli in modo coerente.",
        "calcola": "esegue calcoli basati su elementi presenti nel testo",
        "altro": ""
    }

    @classmethod
    def get_instance(cls, opts: argparse.Namespace = None):
        """
        Access method for the singleton's only instance.
        If it doesn't already exist, it creates and initializes it.
        """
        if cls._instance is None:
            cls._instance = cls(opts)
        return cls._instance

    def __init__(self, opts: argparse.Namespace = None):
        """
        Initializes configuration values only the first time.
        Avoids overwriting values if they've already been initialized.
        """
        if hasattr(self, "_initialized") and self._initialized:
            return

        # Load options from CLI arguments if provided
        if opts:
            if opts.api_key:
                self.api_key = opts.api_key

            if opts.max_iterations and int(opts.max_iterations) > 0:
                self.max_iterations = int(opts.max_iterations)

            if opts.seconds and int(opts.seconds) > 0:
                self.seconds = int(opts.seconds)

        # Instantiate the LLM model with the configured API key
        self.llm = LLM.get_instance(api_key=self.api_key).llm

        # Mark as initialized to avoid double initializations
        self._initialized = True

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