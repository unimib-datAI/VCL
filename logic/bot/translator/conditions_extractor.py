from copy import deepcopy

from utils.config import Config
from utils.DQL_language import DQLLanguage

class ConditionsExtractor:
    """
    Extracts additional constraints, filters, and logical modifiers (the 'how' section) 
    from user queries using LLM-based analysis.

    This component identifies specific limitations (e.g., temporal bounds, numerical 
    constraints) or general conditions that qualify the primary DQL command.

    Responsibilities:
        - Routing queries to specific extraction logic (e.g., Limit extraction).
        - Formatting contextual data (query, command, available docs) for LLM prompts.
        - Parsing and cleaning structured LLM outputs into Python dictionaries.
        - Managing fallback mechanisms for failed or empty extractions.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the ConditionsExtractor with required services.

        Args:
            cfg (Config): Global configuration instance providing the LLM engine,
                          logger, and DQL language definitions.
        """
        self._llm = cfg.get_LLM()
        self._logger = cfg.get_logger("Conditions Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL()
        
        # Helper function to serialize document lists for prompt injection
        self.docs_in_string = cfg.docs_in_string
        
        # Mapping of detected triggers to specialized extraction methods
        self.CONDITIONS_MAP = {
            "LimitExtraction": self.limit_extraction
        }

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def extract(self, query: str, structured_query: dict, docs: list) -> dict:
        """
        Coordinates the multi-stage extraction process for a single query.

        Steps:
            1. Routes the query to check for specific condition types (e.g., limits).
            2. Executes specialized extractors based on router findings.
            3. Performs a general 'additional conditions' extraction for broad context.
            4. Merges and returns all identified conditions.

        Args:
            query (str): The raw natural language input.
            structured_query (dict): The command/what/from data identified so far.
            docs (list): Metadata of documents involved in the request.

        Returns:
            dict: The 'how' dictionary containing all extracted constraints.
        """
        # Initialize the 'how' container
        structured_query["how"] = {}
        
        # Step 1: Detect which specialized extractors should be triggered
        conditions_router = self.conditions_router(query)
        
        for key, value in conditions_router.items():
            # Check if the router explicitly identified a specific condition type
            if not isinstance(value, str) or value.lower() != "yes":
                continue

            # Invoke the specialized extraction method from the map
            specific_conditions = self.CONDITIONS_MAP[key](query)

            # Filter out empty or invalid results
            if isinstance(specific_conditions, dict) and not all(v != "" for v in specific_conditions.values()):
                continue

            # Format the key (e.g., 'LimitExtraction' -> 'limit') and store result
            new_key = key.replace("Extraction", "").lower()
            structured_query["how"][new_key] = specific_conditions
        
        # Step 2: Extract broad/general conditions that might not match specialized triggers
        additional_conditions = self.additional_conditions(query, structured_query, docs)
        structured_query["how"].update(additional_conditions)
        
        return structured_query["how"]
        
    def conditions_router(self, query: str):
        """
        Classification step that determines which specialized extraction prompts 
        are relevant for the given query.
        """
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get("ConditionsRouter.json", None)
            
            if not prompt:
                raise ValueError("ConditionsRouter.json prompt template missing.")
            
            if query.strip():
                # Call LLM to categorize the types of conditions present
                conditions = self._llm.invoke(
                    prompt,
                    {"query": query}
                )
                status = "Done"
            else:
                raise ValueError("Received empty query.")

        except Exception as e:
            self._logger.error(f"Conditions Router execution failed: {e}")
            conditions = {}

        self._logger.info(f"Router Conditions -> {conditions} ({status})")
        return conditions
        
    def limit_extraction(self, query: str) -> dict:
        """
        Specialized extractor for numerical or boundary constraints (e.g., 'only the first 5').
        """
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get("LimitExtraction.json", None)
            
            if not prompt:
                raise ValueError("LimitExtraction.json prompt template missing.")
            
            if query.strip():
                # Perform extraction with JSON mode enabled (True)
                conditions = self._llm.invoke(
                    prompt,
                    {"query": query},
                    True 
                )
                
                sign = conditions.get("sign", "")
                sign = "~" if sign == "=" else sign # We accept tolerance
                
                status = "Done"
            else:
                raise ValueError("Empty query string.")

        except Exception as e:
            self._logger.error(f"Limit extraction failed: {e}")
            conditions = {}

        self._logger.info(f"Limit Extraction -> {conditions} ({status})")
        return conditions

    def additional_conditions(self, query: str, structured_query: dict, docs: list) -> dict:
        """
        Final broad-sweep extraction to capture any qualifying language 
        not captured by specialized routers.
        """
        # Prepare context-rich input for the LLM
        query_dict = {
            "query": query,
            "structured_query": str(structured_query),
            "documents": self.docs_in_string(docs)
        }

        conditions = {}
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get("AdditionalConditionsExtraction.json", None)
            
            if not prompt:
                raise ValueError("AdditionalConditionsExtraction.json template missing.")
            
            if query_dict.get("query", "").strip():
                # Context-aware extraction
                conditions = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )
                
                # Cleanup: remove keys with empty or null values
                for c in deepcopy(conditions):
                    if not conditions[c]:
                        del conditions[c]

                status = "Done"
            else:
                raise ValueError("Empty query string.")

        except Exception as e:
            self._logger.error(f"General conditions extraction failed: {e}")
            conditions = {}

        self._logger.info(f"General Conditions -> {conditions} ({status})")
        return conditions