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
        
        self.docs_in_string = cfg.docs_in_string
        
        self.CONDITIONS_MAP = {
            "LimitExtraction": self.limit_extraction
        }

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, structured_query: dict, docs: list) -> dict:
        structured_query["how"] = {}
        
        conditions_router = self.conditions_router(query)
        
        for key, value in conditions_router.items():
            if "yes" == value.lower():    
                specific_conditions = self.CONDITIONS_MAP[key](query)
                
                new_key = key.replace("Extraction", "").lower()
                structured_query["how"].update({new_key: specific_conditions})
        
        additional_conditions = self.additional_conditions(query, structured_query, docs)
        structured_query["how"].update(additional_conditions)
        
        return structured_query["how"]
        
    def conditions_router(self, query: str):
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get("ConditionsRouter.json", None)
            
            if not prompt:
                raise ValueError("ConditionsRouter.json prompt not found.")
            
            if query.strip():
                conditions = self._llm.invoke(
                    prompt,
                    {"query": query}
                )

                status = "Done"
            else:
                raise ValueError("Empty query provided to ConditionsRouter.")

        except Exception as e:
            self._logger.error("Conditions Router failed: " + str(e))
            conditions = {}

        self._logger.info(
            f"Condition Router -> {conditions} ({status})"
        )

        return conditions
        
    
    def limit_extraction(self, query: str) -> dict:
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get("LimitExtraction.json", None)
            
            if not prompt:
                raise ValueError("LimitExtraction.json prompt not found.")
            
            if query.strip():
                conditions = self._llm.invoke(
                    prompt,
                    {"query": query},
                    True
                )

                status = "Done"
            else:
                raise ValueError("Empty query provided to LimitExtraction.")

        except Exception as e:
            self._logger.error("Limit extraction failed: " + str(e))
            conditions = {}

        self._logger.info(
            f"\"{query}\" -> {conditions} ({status})"
        )

        return conditions

    def additional_conditions(self, query: str, structured_query: dict, docs: list) -> dict:
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