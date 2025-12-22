from copy import deepcopy

from utils.config import Config
from utils.DQL_language import DQLLanguage

class ConditionsExtractor:
    """
    Extracts additional conditions or constraints (the 'how') from user
    queries using an LLM.

    Responsibilities:
        - Format the query and its context (command, what, from) for the LLM.
        - Invoke the LLM to extract conditions.
        - Convert LLM output (expected to be JSON/dict) into a dictionary.
        - Log results and handle errors gracefully.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the ConditionsExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration instance providing logger, LLM,
                          and DQL language data.
        """
        self._llm = cfg.get_LLM()
        self._logger = cfg.get_logger("Conditions Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL()

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, structured_query: dict, docs: list) -> dict:
        """
        Extract additional conditions ('how') from a user query.

        Steps:
            1. Prepare the input dictionary for the LLM, including the raw
               query, the structured query, and document context.
            2. Invoke the LLM to extract conditions.
            3. Convert the result into a dictionary.
            4. Handle empty queries or errors with a fallback (empty dict).

        Args:
            query (str): The raw user input query.
            structured_query (dict): Structured representation of the query
                              (containing 'command', 'what', 'from').
            docs (list): A list of document tuples (name, reference)
                         extracted in a previous step.

        Returns:
            dict: Extracted conditions as key-value pairs (e.g.,
                  {"format": "list", "language": "english"}).
        """
        # Prepare the input dictionary for the LLM prompt
        query_dict = {
            "query": query,
            "structured_query": str(structured_query),
            "documents": self.docs_in_string(docs)
        }

        conditions = {}
        status = "Error"  # Initial status for logging

        try:
            # Retrieve the specific prompt for condition extraction
            prompt = self._dql_language.prompts.get("AdditionalConditionsExtraction.json", None)
            
            if not prompt:
                raise ValueError("AdditionalConditionsExtraction.json prompt not found.")
            
            # Only process if the original query was non-empty
            if query_dict.get("query", "").strip():
                # Invoke LLM to extract conditions
                conditions = self._llm.invoke(
                    prompt,
                    query_dict,
                    True  # Assuming this flag enables JSON/dict mode
                )
                
                for c in deepcopy(conditions):
                    if not conditions[c]:
                        del conditions[c]

                status = "Done"
            else:
                raise ValueError("Empty query provided to ConditionsExtractor.")

        except Exception as e:
            # Fallback to an empty dictionary in case of any error
            self._logger.error("Conditions extraction failed: " + str(e))
            conditions = {}

        # Log the extraction result
        self._logger.info(
            f"\"{query}\" -> {conditions} ({status})"
        )

        return conditions
    
    @staticmethod
    def docs_in_string(docs):
        info = [
            f"- con la stringa \"{doc[1]}\" l'utente fa riferimento al documento \"{doc[0]}\""
            for doc in docs
            if len(doc) == 2 and doc[0] != doc[1]
        ]
        
        return "\n\t\t".join(info).strip()