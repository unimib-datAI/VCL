import itertools

from utils.config import Config
from utils.DQL_language import DQLLanguage

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
        self._logger = cfg.get_logger("Planner")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------
    
    def decompose(self, query: dict) -> list[dict]:
        """
        Decompose a structured query into a list of operations.

        Logic:
            - If the command is a "middle command" (like 'search') and has
              multiple sources, it creates individual operations for each
              source, followed by an "integration" operation.
            - If the command is a "middle command" but has only one source,
              it's returned as a single operation.
            - If the command is not a "middle command" (it's a final command),
              it finds a suitable middle command to execute on each source
              first, then adds the original final command as the last step.

        Args:
            query (dict): Structured query containing keys 'command', 'from',
                          'what', and 'how'.

        Returns:
            list[dict]: List of operation dictionaries ready for execution.
        """
        command_key = query.get("command", "")

        # Find the appropriate intermediate command(s) based on 'what' is being requested
        middle_commands = self._find_middle_commands(query.get("what", ""))
        
        # Case 1: The query's command is already an intermediate command
        if command_key in middle_commands:
            # If it applies to more than one source, we must split it
            if len(query.get("from", [])) > 1:
                self._logger.info("Decomposition required: Splitting one command across multiple sources.")
                # 'integra' is the domain-specific command for merging results
                return self._create_operations(query, command_key, "integra")
            else:
                # Only one source, no decomposition needed
                self._logger.info("No decomposition required: Single operation.")
                return [query]
        elif command_key == "riassumi" and len(query.get("from", [])) > 1:
            middle_step = [
                {
                    "id": f"{query.get('id', '')}_{i}",
                    "command": command_key,
                    "from": [source],
                    "what": query.get("what", "")
                }
                for i, source in enumerate(query.get("from", []))
            ]
            
            last_ids = [op.get("id", "") for op in middle_step]
            
            final_op = {
                "id": f"{query.get('id', '')}",
                "command": "integra",
                "from": last_ids,
                "what": query.get("what", ""),
                "how": query.get("how", {})
            }
            
            ops = []
            
            for op in middle_step:
                ops.append(self._create_operations(op, middle_commands[0], command_key))
                
            ops = list(itertools.chain.from_iterable(
                x if isinstance(x, list) else [x] for x in ops
            ))
            ops.append(final_op)
            
            return ops
                
        # Case 3: The query's command is a final command (e.g., 'summarize')
        # We must first run the appropriate middle command (e.g., 'search')
        # on all sources, and then run the final command.
        self._logger.info("Decomposition required: Creating intermediate and final operations.")
        return self._create_operations(query, middle_commands[0], command_key)

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------
    
    def _create_operations(self, query: dict, middle_command: str, final_command: str) -> list[dict]:
        """
        Generate the list of operations including intermediate and final commands.

        Args:
            query (dict): The original structured query.
            middle_command (str): Intermediate command to run on each source
                                  (e.g., 'cerca').
            final_command (str): The final command to execute after
                                 decomposition (e.g., 'integra' or 'riassumi').

        Returns:
            list[dict]: List of operations, including the final
                        aggregation operation.
        """
        # Create atomic operations for each source using the middle_command
        atomic_ops = [
            {
                "id": f"{query.get('id', '')}_{i}",
                "command": middle_command,
                "from": [source],
                "what": query.get("what", "")
                # 'how' is usually applied only to the final operation
            }
            for i, source in enumerate(query.get("from", []))
        ]
        
        self._logger.info(f"Found {len(atomic_ops)} sub-operations:")
        for i, op in enumerate(atomic_ops):
            str_command = op.get("command", "")
            str_from = str(op.get("from", []))
            str_what = op.get("what", "")
            str_how = "None"
            self._logger.info(f"\t- {str(i)}: {str_command}({str_from}, {str_what}, {str_how})")

        # Create the final aggregation operation
        final_op = {
            "id": query.get("id", ""),
            "command": final_command,
            # The 'from' for the final op is the list of IDs from the atomic ops
            "from": [op["id"] for op in atomic_ops],
            "what": query.get("what", ""), # Pass 'what' along
            "how": query.get("how", {}) # Apply conditions here
        }

        i = len(atomic_ops)
        
        self._logger.info("Final aggregation operation:")
        str_command = final_op.get("command", "")
        str_from = str(final_op.get("from", []))
        str_what = final_op.get("what", "")
        str_how = str(final_op.get("how", ""))
        self._logger.info(f"\t- {str(i+1)}: {str_command}({str_from}, {str_what}, {str_how})")
            
        atomic_ops.append(final_op)
        return atomic_ops

    def _find_middle_commands(self, what: str) -> list[str]:
        """
        Identify the intermediate command(s) that match the 'what' field.

        This checks the DQL configuration to see which command is
        associated with extracting a specific 'what' (e.g., extracting
        'price' might map to a 'find_price' command).

        Args:
            what (str): The target content of the query.

        Returns:
            list[str]: A list of possible middle command keys. Defaults to
                       the default command if no specific one is found.
        """
        # 'intero documento' is a special case mapping to 'cerca'
        if what == "intero documento":
            self._logger.info("Possible Middle Commands: ['cerca'] (for 'intero documento')")
            return ["cerca"]
        
        # Look up the 'what' in the DQL configuration
        for what_dict in self._dql_language.get_what():
            if what == what_dict.get("name", ""):
                # Check if it has a specific command associated with it
                if len((w := what_dict.get("relative_command", []))) > 0:
                    self._logger.info(f"Possible Middle Commands: {w}")
                    return w
                break
                
        # Fallback to the system's default command
        self._logger.info("Possible Middle Commands: Not found. Using default command.")
        return [self._dql_language.default_command.get("command", "")]