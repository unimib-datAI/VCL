from utils.config import Config
from utils.DQL_language import DQLLanguage


class CommandClassifier:
    """
    Classifies user queries into predefined commands using the LLM and
    the application's DQL language configuration.

    Responsibilities:
        - Transform the query into a structured format for the LLM.
        - Invoke the LLM to classify the intent of the query.
        - Retrieve command information (name and description) from DQLLanguage.
        - Provide a fallback for unrecognized queries.
        - Log classification results for traceability.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    def __init__(self, cfg: Config):
        """
        Initialize the CommandClassifier with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger,
                          LLM instance, and DQL language data.
        """
        self._llm = cfg.llm
        self._logger = cfg.get_logger("Command Classifier")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # ----------------------------------
    # --- Main Classification Method ---
    # ----------------------------------
    
    def classify(self, query: str) -> dict:
        """
        Classify the user query into a DQL command.

        Steps:
            1. Prepare the query and available commands for the LLM.
            2. Call the LLM to determine the intent.
            3. Map the result to a command name and description.
            4. Handle unknown queries with a default fallback.

        Args:
            query (str): User input query to classify.

        Returns:
            dict: Dictionary containing 'name' and 'description' of
                  the classified command.
        """

        # Prepare the input dictionary for the LLM prompt
        query_dict = {
            "query": query,
            "feedback": ""  # Placeholder
        }

        command_info = {}
        status = "Error"  # Initial status for logging

        try:
            # Retrieve the correct prompt for intent classification
            prompt = self._dql_language.prompts.get("IntentClassification.json", None)
            
            if not prompt:
                raise ValueError("IntentClassification.json prompt not found.")
            
            # Only process non-empty queries
            if query_dict.get("query", "").strip():
                # Invoke the LLM to classify the query
                llm_result = self._llm.invoke(
                    prompt,
                    query_dict,
                    True
                )

                # Map the LLM result (e.g., a key) to a standardized command name
                command_key = self._dql_language.get_command_from_key(llm_result)

                # Retrieve full command information
                command_info = {
                    "name": command_key,
                    "description": self._dql_language.get_description_from_command(command_key)
                }

                status = "Done"
            else:
                raise ValueError("Empty query provided to CommandClassification.")

        except Exception as e:
            self._logger.error(f"Command classification failed: {e}. Falling back to default.")
            # Fallback to the default 'altro' (other) command in case of any error
            default_key = "altro"
            command_info = {
                "name": default_key,
                "description": self._dql_language.get_description_from_command(default_key)
            }

        # Log the classification result
        self._logger.info(
            f"Intent Classification: {command_info.get('name', 'altro')} - {status}"
        )

        return command_info