import os
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
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Sources Extractor")
        self.project_root = cfg.project_root
        self.dql_language: DQLLanguage = cfg.language

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
        language_sources_str = self.sources_string(self.dql_language.get_sources())

        query_dict = {
            "query": query,
            "language_sources": language_sources_str,
            "number": len(self.dql_language.get_sources()),
            "feedback": ""
        }

        documents = []
        status = "Error"

        try:
            prompt = self.dql_language.prompts.get("ExplicitDocumentsExtraction.json", None)
            
            if not prompt:
                raise ValueError("Error during prompt retrieval")
            
            if query_dict.get("query", "").strip():
                # Invoke LLM to select relevant documents
                documents = self.llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                status = "Done"
            else:
                raise ValueError("Empty query provided to SourcesExtractor.")

        except Exception as e:
            # Fallback: return all available sources
            documents = [[src["name"], src["name"]] for src in self.dql_language.get_sources()]

        # Log the extraction result
        self.logger.info(f"Sources Extractor: {documents} - {status}")

        return documents

    # -------------------------------------------------------------------------
    # Helper Method
    # -------------------------------------------------------------------------
    @staticmethod
    def sources_string(sources: list) -> str:
        """
        Generate a formatted string of available sources for LLM input or logging.

        Args:
            sources (list): List of source dictionaries with 'name', 'description', and 'synonyms'.

        Returns:
            str: A formatted string listing all available sources and synonyms.
        """
        synonyms = [
            f"'{synonym.strip()}'" for src in sources for synonym in src.get("synonyms", [])
        ]

        sources_list = [
            f'\t\t- "{src["name"]}" (or {",".join(synonyms[index])}): {src["description"]}'
            for index, src in enumerate(sources)
        ]

        if sources_list:
            sources_list = ["\t- \"Legal Documents\": Only the following are available:"] + sources_list

        return "\n".join(sources_list)
