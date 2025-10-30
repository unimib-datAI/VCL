import os
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
        self.llm = cfg.llm
        self.logger = cfg.get_logger("Command Classifier")
        self.project_root = cfg.project_root
        self.dql_language: DQLLanguage = cfg.language

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
            dict: Dictionary containing 'name' and 'description' of the classified command.
        """
        language_commands_str = self.commands_string(self.dql_language.commands)

        query_dict = {
            "query": query,
            "language_commands": language_commands_str,
            "default_key": self.dql_language.default_command.get("key", ""),
            "feedback": ""
        }

        command_info = {}
        status = "Error"

        try:
            # Only process non-empty queries
            if query_dict.get("query", "").strip():
                # Invoke the LLM to classify the query
                llm_result = self.llm.invoke(
                    os.path.join(
                        self.project_root,
                        "documents",
                        "prompts",
                        "rewriting",
                        "3 - IntentClassification.json"
                    ),
                    query_dict,
                    True
                )

                # Map the LLM result to a command key
                command_key = self.dql_language.get_command_from_key(llm_result)

                # Retrieve command information
                command_info = {
                    "name": command_key,
                    "description": self.dql_language.get_description_from_command(command_key)
                }

                status = "Done"
            else:
                raise ValueError("Empty query provided")

        except Exception:
            # Fallback to default 'altro' command for errors
            command_info = {
                "name": "altro",
                "description": self.dql_language.get_description_from_command("altro")
            }

        # Log the classification result
        self.logger.info(
            f"Intent Classification: {command_info.get('name', 'altro')} - {status}"
        )

        return command_info

    # ----------------------
    # --- Helper Methods ---
    # ----------------------
    
    @staticmethod
    def commands_string(commands) -> str:
        """
        Generate a formatted string of available commands for logging or display.

        Args:
            commands (list[dict]): List of command dictionaries with 'key' and 'description'.

        Returns:
            str: A formatted string listing all available commands.
        """
        commands_list = [
            f"- \"{cmd['key']}\": {cmd['description']}" for cmd in commands
        ]
        return "\n".join(commands_list)
