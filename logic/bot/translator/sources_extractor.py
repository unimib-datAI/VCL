import re

from utils.config import Config
from utils.DQL_language import DQLLanguage

class SourcesExtractor:
    """
    Extracts relevant sources/documents from a user query using an LLM.

    Responsibilities:
        - Prepare the list of available sources for the LLM.
        - Invoke the LLM to select sources relevant to the query.
        - Provide a fallback to all sources if extraction fails.
        - Log extraction results for traceability.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the SourcesExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger, LLM, and DQL language data.
        """
        self._llm = cfg.llm
        self._storage = cfg.storage
        self._logger = cfg.get_logger("Sources Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, user_id, chat_id, tasks_id: list) -> list:
        documents = self._explicit_documents_extraction(query) + self._implicit_documents_extraction(query, user_id, chat_id) + self._task_id_extraction(query, tasks_id)
        documents = [d for d in documents if not str(d[0]).startswith("#")]
        self._logger.info(str(documents))
        return documents
    
    def _explicit_documents_extraction(self, query: str) -> list:
        """
        Extract relevant sources/documents from a user query.

        Steps:
            1. Prepare the query and list of available sources.
            2. Call the LLM to identify relevant documents.
            3. Convert LLM output into a list of document names.
            4. Fallback to all available sources if extraction fails.

        Args:
            query (str): User input query to extract sources from.

        Returns:
            list: List of document/source names deemed relevant.
        """

        query_dict = {
            "query": query,
            "feedback": ""
        }

        documents = []
        status = "Error"
        
        try:
            # Retrieve the specific prompt for 'sources' extraction
            prompt = self._dql_language.prompts.get("ExplicitDocumentsExtraction.json", None)
            
            if not prompt:
                raise ValueError("ExplicitDocumentsExtraction.json prompt not found.")
            
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract from query
                documents = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                status = "Done"
            else:
                raise ValueError("Empty query provided to ExplicitDocumentsExtraction.")
        except Exception as e:
            # Fallback: return all available sources
            documents = [[src["name"], src["name"]] for src in self._dql_language.get_sources()]

        # Log the extraction result
        self._logger.info(f"Sources Extractor: {documents} - {status}")

        return documents
    
    def _implicit_documents_extraction(self, query, user_id, chat_id) -> list:
        chat = self._storage.get_chat_messages(user_id, chat_id)
        
        chat_str = str(
            [
                {
                    "id": c.get("full_details", {}).get("id", ""), 
                    "prompt": c.get("full_details", {}).get("prompt", ""), 
                    "used_documents": c.get("full_details", {}).get("used_documents", [])
                } 
                for c in chat if c.get("role", "user") != "user"
            ]
        )
        
        query_dict = {
            "query": query,
            "feedback": "",
            "chat": chat_str
        }

        documents = []
        status = "Error"
        
        try:
            # Retrieve the specific prompt for 'sources' extraction
            prompt = self._dql_language.prompts.get("ImplicitDocumentsExtraction.json", None)
            
            if not prompt:
                raise ValueError("ImplicitDocumentsExtraction.json prompt not found.")
            
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract from query
                documents = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                status = "Done"
            else:
                raise ValueError("Empty query provided to ImplicitDocumentsExtraction.")
        except Exception as e:
            # Fallback: return all available sources
            documents = []

        # Log the extraction result
        self._logger.info(f"Sources Extractor: {documents} - {status}")

        return documents
    
    
    def _task_id_extraction(self, query: str, ids) -> list:
        found_ids = [int(x) for x in re.findall(r"#(\d+)", query)]
        return [[ids[i - 1], f"#{i}"] for i in found_ids if i <= len(ids)]