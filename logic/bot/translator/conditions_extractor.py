import os
from utils.config import Config


class ConditionsExtractor:
    """
    Extracts additional conditions or constraints from user queries using an LLM.

    Responsibilities:
        - Format query input for the LLM.
        - Invoke the LLM to extract conditions.
        - Convert LLM output into a dictionary.
        - Log results and handle errors gracefully.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the ConditionsExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration instance providing logger, LLM, and project paths.
        """
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Conditions Extractor")
        self.project_root = cfg.project_root

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, query_str: dict) -> dict:
        """
        Extract additional conditions from a user query.

        Steps:
            1. Prepare the input dictionary for the LLM.
            2. Invoke the LLM to extract conditions.
            3. Convert the result into a dictionary.
            4. Handle empty queries or errors with fallback.

        Args:
            query (str): The user input query.
            query_str (dict): Structured representation of the query (e.g., parsed components).

        Returns:
            dict: Extracted conditions as key-value pairs.
        """
        query_dict = {
            "query": query,
            "query_str": str(query_str),
            "feedback": "",
            "what": query_str.get("what", "")
        }

        conditions = {}
        status = "Error"

        try:
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract conditions
                llm_result = self.llm.invoke(
                    os.path.join(
                        self.project_root,
                        "documents",
                        "prompts",
                        "rewriting",
                        "7 - AdditionalConditionsExtraction.json"
                    ),
                    query_dict,
                    True
                )

                # Convert LLM output to dictionary
                conditions = self.llm.str_in_dict(llm_result)
                status = "Done"

        except Exception as e:
            # Fallback for errors
            conditions = {}
            status = "Error"
            self.logger.error(f"Error extracting conditions: {e}")

        # Log the extraction result
        self.logger.info(f"Conditions Extractor: {conditions} - {status}")

        return conditions
