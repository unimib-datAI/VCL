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

        middle_commands = self._find_middle_commands(query.get("what", ""))
        
        if command_key in middle_commands:
            if len(query.get("from", [])) > 1:
                self.logger.info("Need to create suboperations")
                return self._create_operations(query, command_key, "integra")
            else:
                self.logger.info("No need to create suboperations")
            return [query]

        self.logger.info("Need to create suboperations")
        return self._create_operations(query, middle_commands[0], command_key)

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
        
        self.logger.info(f"Found {len(atomic_ops)} suboperations:")
        for i, o in enumerate(atomic_ops):
            str_command = o.get("command", "")
            str_from = str(o.get("from", []))
            str_what = o.get("what", "")
            str_how = "None"
            self.logger.info(f"\t- {str(i)}: {str_command}({str_from}, {str_what}, {str_how})")

        # Create the final aggregation operation
        final_op = {
            "id": query.get("id", ""),
            "command": final_command,
            "from": [op["id"] for op in atomic_ops],
            "how": query.get("how", {})
        }

        self.logger.info(f"Final suboperation:")
        str_command = final_op.get("command", "")
        str_from = str(final_op.get("from", []))
        str_what = "None"
        str_how = str(final_op.get("how", ""))
        self.logger.info(f"\t- {str(i)}: {str_command}({str_from}, {str_what}, {str_how})")
            
        atomic_ops.append(final_op)
        return atomic_ops

    def _find_middle_commands(self, what: str) -> str:
        """
        Identify the intermediate command that matches the 'what' field.

        Args:
            what (str): The target content of the query.

        Returns:
            str: The middle command key or empty string if not found.
        """
        for what_dict in self.dql.get_what():
            if what == what_dict.get("name", ""):
                if len((w := what_dict.get("relative_command", []))) > 0:
                    self.logger.info(f"Possible Middle Commands: {w}")
                    return w
                break
            
        self.logger.info("Possible Middle Commands: not found -> default command")
        return self.dql.default_command.get("command", "")
