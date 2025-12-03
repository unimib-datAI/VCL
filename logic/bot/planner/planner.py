from copy import deepcopy

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
        self._sources_name = [src.get("name", "") for src in self._dql_language.get_sources()]

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------
    
    def decompose(self, operations: list[dict]) -> list[dict]:
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
        
        for op in operations:
            id = op.get("id", "")
            structured_prompt = op.get("structured_prompt", {})
            
            command_key = structured_prompt.get("command", "altro")
            from_key = structured_prompt.get("from", [])
            what_key = structured_prompt.get("what", "altro")

            if command_key != "altro":
                # Find the appropriate intermediate command(s) based on 'what' is being requested
                middle_commands = self._find_middle_commands(what_key)
            
                # Case 1: The query's command is already an intermediate command
                if command_key in middle_commands:
                    # If it applies to more than one source, we must split it
                    if len(from_key) > 1:
                        # 'integra' is the domain-specific command for merging results
                        op['operations'] = self._create_operations(structured_prompt, command_key, "integra", id)
                else:
                    # Case 3: The query's command is a final command (e.g., 'summarize')
                    # We must first run the appropriate middle command (e.g., 'search')
                    # on all sources, and then run the final command.
                    if not self._decomposition_in_previous_op(structured_prompt):
                        if command_key == "riassumi":
                            op["operations"] = self._decompose_summarize(structured_prompt, middle_commands[0], id)
                        else:
                            op['operations'] = self._create_operations(structured_prompt, middle_commands[0], command_key, id)
        
        return operations

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------
    
    def _create_operations(self, query: dict, middle_command: str, final_command: str, id) -> list[dict]:
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
        atomic_ops = []
        not_used_sources = []
        for i, source in enumerate(query.get("from", [])):
            if source in self._sources_name:
                atomic_ops.append(
                    {
                        "id": f"{id}_{i}",
                        "structured_prompt": {
                            "command": middle_command,
                            "from": [source],
                            "what": query.get("what", "")
                            # 'how' is usually applied only to the final operation
                        }
                    }
                )
            else:
                not_used_sources.append(source)

        # Create the final aggregation operation
        final_op = {
            "id": id,
            "structured_prompt": {
                "command": final_command,
                "from": [op["id"] for op in atomic_ops] + not_used_sources,
                "what": query.get("what", ""), # Pass 'what' along
                "how": query.get("how", {}) # Apply conditions here
            }
        }
            
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
        # 'intero documento' and 'altro' are special cases
        if what in ["intero documento", "altro"]:
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
        return [self._dql_language.default_command.get("command", "altro")]
    
    def _decomposition_in_previous_op(self, structured_prompt):
        for from_key in structured_prompt.get("from", []):
            if from_key in self._sources_name:
                return False
            
        return True
    
    def _decompose_summarize(self, query, middle_command, id):
        ops = self._create_operations(query, middle_command, "integra", id)
        
        length = str(len(ops) - 1)
        
        old_id = deepcopy(ops[-1]["id"])
        new_id = f"{old_id}_{length}"
        old_how = deepcopy(ops[-1]["structured_prompt"].get("how", {}))
        
        ops[-1]["id"] = new_id
        
        if "how" in ops[-1]["structured_prompt"]:
            del ops[-1]["structured_prompt"]["how"]
            
        if len(ops) == 2:
            del ops[-1]
            
        ops.append(
            {
                "id": id,
                "structured_prompt": {
                    "command": "riassumi",
                    "from": [ops[-1]["id"]],
                    "what": "intero documento",
                    "how": old_how
                }
            }
        )
        
        return ops
        