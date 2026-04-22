from utils.config import Config
from utils.DQL_language import DQLLanguage


class CommandClassifier:
    """
    Classifies user queries into predefined DQL commands using an LLM.

    This component acts as an intent recognizer that maps natural language 
    input to the specific operational categories defined in the DQL 
    language specification (e.g., retrieval, analysis, comparison).

    Responsibilities:
        - Mapping queries to the DQL command taxonomy.
        - Leveraging LLM reasoning with domain-specific prompts.
        - Managing fallbacks for ambiguous or empty inputs.
        - Ensuring traceability via structured logging.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config, user_id: str, request_id: str):
        """
        Initialize the Classifier with necessary engine and language dependencies.

        Args:
            cfg (Config): Global configuration providing access to the LLM 
                          wrapper, logging services, and DQL grammar.
            user_id (str): The unique identifier for the user.
            request_id (str): The unique identifier for the current request.
        """
        # Inject dependencies from the central configuration
        self._llm = cfg.get_LLM()
        self._logger = cfg.get_logger("Command Classifier", request_id)
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL(user_id)

    # ----------------------------------
    # --- Main Classification Method ---
    # ----------------------------------
    
    def classify(self, query: str) -> str:
        """
        Processes a raw query string to identify the intended DQL command.

        The classification logic follows these steps:
            1. Loading the 'IntentClassification' prompt template.
            2. Formatting the user query for LLM consumption.
            3. Parsing the LLM output to match a valid command key.
            4. Defaulting to 'altro' if no clear intent is identified.

        Args:
            query (str): The natural language string provided by the user.

        Returns:
            str: The internal 'name' or 'key' of the identified command.
        """

        # Wrap query in a dictionary for template injection
        query_dict = {
            "query": query
        }

        command = {}
        status = "Error"  # Default status for error tracking

        try:
            # Load the system prompt specifically designed for intent recognition
            prompt = self._dql_language.prompts.get("it", {}).get("IntentClassification.json", None)
            
            if not prompt:
                raise ValueError("IntentClassification.json prompt template is missing from language config.")
            
            # Input validation: ensure the query is not just whitespace
            if query_dict.get("query", "").strip():
                # Call the LLM with the formatted prompt and query data
                # The 'True' flag indicates expected JSON or structured output processing
                command = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )

                # Cross-reference LLM output with the defined DQL command set
                command = self._dql_language.get_command_from_key(command)

                status = "Done"
            else:
                raise ValueError("Empty query string received.")

        except Exception as e:
            # Safety Fallback: 'altro' (other) ensures the pipeline doesn't crash on unrecognized input
            self._logger.error(f"Classification pipeline exception: {e}")
            command = "altro"

        # Record the outcome for auditing and performance monitoring
        self._logger.info(
            f"Intent mapping: \"{query}\" -> {command} (Status: {status})"
        )

        return command