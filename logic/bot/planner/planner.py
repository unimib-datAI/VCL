import os
from utils.config import Config
from utils.DQL_language import DQLLanguage
from utils.file_manager import FileHandler


class Planner:
    """
    Planner class for decomposing structured queries into smaller operations.

    Responsibilities:
        - Decompose high-level commands into atomic operations.
        - Handle multiple sources and intermediate commands.
        - Provide structured operations ready for downstream execution.
    """

    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Planner with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger,
                          project paths, and DQL language data.
        """
        self.logger = cfg.get_logger("Planner")
        self.project_root = cfg.project_root
        self.dql: DQLLanguage = cfg.language
        self.commands = self._retrieve_commands()

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------
    def decompose(self, query: dict) -> list[dict]:
        """
        Decompose a structured query into a list of operations.

        Logic:
            - If the command has atomic sub-commands and multiple sources, create individual operations.
            - If the command is simple, return it as a single operation.
            - Otherwise, find a suitable intermediate command for decomposition.

        Args:
            query (dict): Structured query containing keys 'command', 'from', 'what', and 'how'.

        Returns:
            list[dict]: List of operation dictionaries ready for execution.
        """
        command_key = query.get("command", "")
        sources = query.get("from", [])

        if self.commands.get(command_key, ["*"]):
            if len(sources) > 1:
                return self._create_operations(query, command_key, "integra")
            return [query]

        middle_command = self._find_middle_command(query.get("what", ""))
        return self._create_operations(query, middle_command, command_key)

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------
    def _create_operations(self, query: dict, middle_command: str, final_command: str) -> list[dict]:
        """
        Generate the list of operations including intermediate and final commands.

        Args:
            query (dict): The original structured query.
            middle_command (str): Intermediate command to split operations.
            final_command (str): The final command to execute after decomposition.

        Returns:
            list[dict]: List of operations including final aggregation operation.
        """
        # Create atomic operations for each source
        atomic_ops = [
            {
                "id": f"{query.get('id', '')}_{i}",
                "command": middle_command,
                "from": [source],
                "what": query.get("what", "")
            }
            for i, source in enumerate(query.get("from", []))
        ]

        # Create the final aggregation operation
        final_op = {
            "id": query.get("id", ""),
            "command": final_command,
            "from": [op["id"] for op in atomic_ops],
            "how": query.get("how", {})
        }

        atomic_ops.append(final_op)
        return atomic_ops

    def _find_middle_command(self, what: str) -> str:
        """
        Identify the intermediate command that matches the 'what' field.

        Args:
            what (str): The target content of the query.

        Returns:
            str: The middle command key or empty string if not found.
        """
        for key, atomic_list in self.commands.items():
            if what in atomic_list:
                self.logger.info(f"Middle Command: {key}")
                return key
        self.logger.info("Middle Command: not found")
        return ""

    def _retrieve_commands(self) -> dict:
        """
        Retrieve and structure atomic commands from the DQL language.

        Returns:
            dict: Mapping of command keys to their atomic sub-commands.
        """
        commands_mapping = {}
        for command in self.dql.commands:
            key = command.get("command", "")
            if key:
                commands_mapping[key] = command.get("atomic", [])
        return commands_mapping
