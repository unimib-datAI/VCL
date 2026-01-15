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
        
        self._force_conditions = {
            "LimitExtraction": "riassumi",
            "OrderExtraction": "riorganizza",
            "ClassesExtraction": "classifica"
        }
        
        self._default_conditions = {
            "ConditionsRouter": {"LimitExtraction": "no", "OrderExtraction": "no", "ClassesExtraction": "no"},
            "LimitExtraction": {"sign": "%", "number": 80, "unit": "parole"},
            "OrderExtraction": {"criteria": "Alfanumerico", "direction": "Crescente"},
            "ClassesExtraction": []
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
        conditions_router = self.extraction(query)
        
        for key, value in conditions_router.items():
            # Check if the router explicitly identified a specific condition type
            force_by_command = self._force_conditions.get(key, "") == structured_query.get("command", "").lower()
            
            if force_by_command or (isinstance(value, str) and value.lower() == "yes"):
                # Invoke the specialized extraction method from the map
                specific_conditions = self.extraction(query, key)
                
                if force_by_command and self.is_empty_conditions(specific_conditions):
                    specific_conditions = self._default_conditions.get(key, {})

                # Filter out empty or invalid results
                if self.is_empty_conditions(specific_conditions):
                    continue

                # Format the key (e.g., 'LimitExtraction' -> 'limit') and store result
                new_key = key.replace("Extraction", "").lower()
                structured_query["how"][new_key] = specific_conditions
        
        # Step 2: Extract broad/general conditions that might not match specialized triggers
        additional_conditions = self.additional_conditions(query, structured_query, docs)
        
        if additional_conditions:
            structured_query["how"].update({"others": additional_conditions})
        
        return structured_query["how"]
    
    def is_empty_conditions(self, conditions: dict) -> bool:
        """
        Check if the extracted conditions dictionary is empty or contains only empty values.

        Args:
            conditions (dict): The conditions dictionary to check.
        Returns:
            bool: True if empty or all values are empty, False otherwise.
        """
        return not conditions or all(v == "" for v in conditions.values())

    def extraction(self, query: str, name = "ConditionsRouter") -> dict:
        status = "Error"

        try:
            prompt = self._dql_language.prompts.get(f"{name}.json", None)
            
            if not prompt:
                raise ValueError(f"{name}.json prompt template missing.")
            
            if query.strip():
                conditions = self._llm.invoke(
                    prompt,
                    {"query": query}, 
                )
                
                if name == "LimitExtraction":
                    # Normalize the sign representation
                    sign = conditions.get("sign", "")
                    conditions["sign"] = "~" if sign == "=" else sign # We accept tolerance
                
                if not isinstance(conditions, list):
                    # Cleanup: ensure we return a dict    
                    if conditions is None or (not isinstance(conditions, dict)):
                        conditions = {}
                        
                    for k, v in deepcopy(conditions).items():
                        # Cleanup: remove keys with empty or null values
                        if v is None or (isinstance(v, str) and not v.strip()):
                            conditions[k] = self._default_conditions.get(name, {}).get(k, v)
                
                status = "Done"
            else:
                raise ValueError("Empty query string.")

        except Exception as e:
            self._logger.error(f"{name} failed: {e}")
            conditions = {}

        self._logger.info(f"{name} -> {conditions} ({status})")
        return conditions

    def additional_conditions(self, query: str, structured_query: dict, docs: list) -> dict:
        """
        Final broad-sweep extraction to capture any qualifying language 
        not captured by specialized routers.
        """
        conditions = {}
        status = "Error"

        try:
            # Prepare context-rich input for the LLM
            query_dict = {
                "query": query,
                "structured_query": str(structured_query),
                "documents": self.docs_in_string(docs),
                "description_command": self._dql_language.get_description_from_command(structured_query.get("command")),
                "description_what": "\n".join(f"\t- {w}: \"{self._dql_language.get_description_from_what(w)}\"" for w in structured_query.get("what", [])),
            }
        
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