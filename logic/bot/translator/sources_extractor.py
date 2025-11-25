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
        self._logger = cfg.get_logger("Sources Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str) -> list:
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
