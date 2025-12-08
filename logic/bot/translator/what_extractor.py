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
            cfg (Config): Global configuration object providing logger, LLM,
                          and DQL language data.
        """
        self._llm = cfg.llm
        self._logger = cfg.get_logger("What Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, sources: list[str]) -> str:
        """
        Extract the 'what' element from a user query given the selected sources.

        Steps:
            1. Prepare the query and available 'what' elements for the LLM.
            2. Invoke the LLM to identify the specific content to extract.
            3. Provide a default fallback if LLM fails or query is empty.
            4. Log the extraction result.

        Args:
            query (str): User input query to analyze.
            sources (list[str]): Relevant sources or documents associated
                                 with the query.

        Returns:
            str: Extracted 'what' content or a default fallback string.
        """
        # Get a formatted string of available 'what' elements based on sources
        available_what = self._dql_language.get_available_what(sources)
        language_what_str = self._what_string(
            available_what
        )

        # Prepare the input dictionary for the LLM prompt
        query_dict = {
            "query": query,
            "what": language_what_str
        }

        what = ""
        status = "Error"  # Initial status for logging

        try:
            # Retrieve the specific prompt for 'what' extraction
            prompt = self._dql_language.prompts.get("WhatExtraction.json", None)
            
            if not prompt:
                raise ValueError("WhatExtraction.json prompt not found.")
            
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract 'what' from query
                what = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                if what not in available_what and what != "altro" and what != "intero documento":
                    self._logger.info(f"What Extractor: \"{what}\" not in available what")
                    what = "altro"
                
                status = "Done"
            else:
                raise ValueError("Empty query provided to WhatExtractor.")

        except Exception as e:
            # Fallback to default value (e.g., "altro") if extraction fails
            what = "altro"
            self._logger.error(f"Error extracting 'what': {e}")

        # Log the extraction result
        self._logger.info(f"What Extractor: {what} - {status}")

        return what

    # ----------------------
    # --- Helper Methods ---
    # ----------------------
    
    @staticmethod
    def _what_string(what_list: list[str]) -> str:
        """
        Generate a formatted string of available 'what' elements for the LLM prompt.

        Args:
            what_list (list[str]): List of 'what' strings.

        Returns:
            str: A newline-separated string listing all 'what' elements.
        """
        return "\n".join(f"- \"{item}\": {what_list[item]}" for item in what_list)