import os
from utils.config import Config
from utils.DQL_language import DQLLanguage


class WhatExtractor:
    """
    Extracts the 'what' elements (specific targets or content) from a user query
    based on available sources using an LLM.

    Responsibilities:
        - Prepare the list of available 'what' elements for the LLM.
        - Invoke the LLM to extract the relevant 'what' content.
        - Provide a fallback default if extraction fails.
        - Log extraction results for traceability.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config):
        """
        Initialize the WhatExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger, LLM, and DQL language data.
        """
        self.llm = cfg.llm
        self.logger = cfg.get_logger("What Extractor")
        self.project_root = cfg.project_root
        self.dql_language: DQLLanguage = cfg.language

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, sources: str) -> str:
        """
        Extract the 'what' element from a user query given the selected sources.

        Steps:
            1. Prepare the query and available 'what' elements for the LLM.
            2. Invoke the LLM to identify the specific content to extract.
            3. Provide a default fallback if LLM fails or query is empty.
            4. Log the extraction result.

        Args:
            query (str): User input query to analyze.
            sources (str): Relevant sources or documents associated with the query.

        Returns:
            str: Extracted 'what' content or a default fallback string.
        """
        language_what_str = self.what_string(self.dql_language.get_available_what(sources))

        query_dict = {
            "query": query,
            "language_what": language_what_str,
            "feedback": ""
        }

        what = ""
        status = "Error"

        try:
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract 'what' from query
                what = self.llm.invoke(
                    os.path.join(
                        self.project_root,
                        "documents",
                        "prompts",
                        "rewriting",
                        "6 - WhatExtraction.json"
                    ),
                    query_dict,
                    True
                )
                status = "Done"
            else:
                raise ValueError("Empty query provided")

        except Exception as e:
            # Fallback to default value if extraction fails
            what = "intero documento"
            self.logger.error(f"Error extracting 'what': {e}")

        # Log the extraction result
        self.logger.info(f"What Extractor: {what} - {status}")

        return what

    # ---------------------
    # --- Helper Method ---
    # ---------------------
    
    @staticmethod
    def what_string(what_elements) -> str:
        """
        Generate a formatted string of available 'what' elements for LLM input or logging.

        Args:
            what_elements (list[tuple]): List of tuples where each tuple contains
                                         ('what_key', 'description').

        Returns:
            str: A formatted string listing all available 'what' elements.
        """
        what_list = [
            f'\t- "{what[0]}": {what[1]}' for what in what_elements
        ]
        return "\n".join(what_list)
