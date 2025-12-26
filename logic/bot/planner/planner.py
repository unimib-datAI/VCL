from typing import List, Dict, Any

from utils.config import Config
from utils.DQL_language import DQLLanguage

class Planner:
    """
    Planner class for decomposing structured queries into smaller, atomic operations.

    Responsibilities:
        - Decompose high-level commands into execution-ready atomic steps.
        - Orchestrate multi-source data retrieval and intermediate processing.
        - Handle command-specific logic like summarization and integration.
    """

    def __init__(self, cfg: Config):
        """
        Initialize the Planner with configuration and language definitions.

        Args:
            cfg (Config): Global configuration object providing logger and DQL data.
        """
        self._logger = cfg.get_logger("Planner")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL()
        self._sources_name = [
            src.get("name", "") for src in self._dql_language.get_sources()
        ]

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def decompose(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Main entry point to decompose a list of high-level operations.

        Args:
            operations (list[dict]): List of operations to analyze.

        Returns:
            list[dict]: Flattened or structured list of executable operations.
        """
        final_plan = []

        for op in operations:
            decomposed_ops = self._process_operation(op)
            
            # If the decomposition produced exactly one operation, flatten it
            if len(decomposed_ops) == 1:
                final_plan.append(decomposed_ops[0])
            else:
                # Keep as a grouped operation if it contains multiple steps
                op['operations'] = decomposed_ops
                final_plan.append(op)

        return final_plan

    # -------------------------------------------------------------------------
    # Private Decomposition Logic
    # -------------------------------------------------------------------------

    def _process_operation(self, op: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processes a single operation and decides the decomposition strategy.
        """
        op_id = op.get("id", "unknown")
        prompt = op.get("structured_prompt", {})
        
        self._logger.info(f"Decomposing operation ID: {op_id}")

        command = prompt.get("command", "altro")
        sources = prompt.get("from", [])
        whats = prompt.get("what", ["altro"])
        how = prompt.get("how", {})

        if command == "altro":
            return [op]

        sub_operations = []
        last_step_ids = []

        # Iterate over each requested element in 'what'
        for what_item in whats:
            start_idx = len(sub_operations)
            processed_steps = self._process_what_element(
                command, sources, what_item, how, op_id, start_idx
            )
            sub_operations.extend(processed_steps)
            
            if processed_steps:
                last_step_ids.append(processed_steps[-1].get("id"))

        # Add a final integration step if multiple 'what' elements were processed
        return self._finalize_integration(sub_operations, last_step_ids, op_id)

    def _process_what_element(self, command: str, sources: list, what: str, 
                             how: dict, parent_id: str, start_idx: int) -> List[Dict]:
        """
        Determines how to handle a specific 'what' attribute for the given sources.
        """
        middle_commands = self._find_middle_commands(what)
        
        # Scenario A: Command is already an intermediate command (e.g., 'search')
        if command in middle_commands:
            if len(sources) > 1:
                self._logger.info(f"Decomposing '{command}' over multiple sources.")
                return self._create_operations(command, "integra", sources, what, how, parent_id, start_idx)
            
            return [self._build_step(parent_id, start_idx, command, sources, [what], how)]

        # Scenario B: Final command (e.g., 'summarize') requiring preliminary data extraction
        if self._need_decomposition(sources, what):
            self._logger.info(f"Decomposing final command '{command}' using {middle_commands[0]}")
            
            if command == "riassumi":
                return self._decompose_summarize(middle_commands[0], sources, what, how, parent_id, start_idx)
            
            return self._create_operations(middle_commands[0], command, sources, what, how, parent_id, start_idx)

        # Scenario C: No decomposition needed
        return [self._build_step(parent_id, start_idx, command, sources, [what], how)]

    # -------------------------------------------------------------------------
    # Operation Builders
    # -------------------------------------------------------------------------

    def _create_operations(self, mid_cmd: str, final_cmd: str, sources: list, 
                          what: str, how: dict, p_id: str, start_idx: int) -> List[Dict]:
        """
        Creates a sequence of atomic extraction steps followed by a final aggregation step.
        """
        # Conflict prevention between search and extract
        if (mid_cmd == "cerca" and "estrai" in final_cmd) or (mid_cmd == "estrai" and "cerca" in final_cmd):
            self._logger.warning("Conflict between 'cerca' and 'estrai' detected.")
            if len(sources) == 1:
                return [self._build_step(p_id, start_idx, mid_cmd, sources, [what], how)]
            return self._create_operations(mid_cmd, "integra", sources, what, how, p_id, start_idx)

        atomic_ops = []
        not_used_sources = []

        # Create steps for specific data sources
        if what != "intero documento":
            for i, src in enumerate(sources, start=start_idx):
                if src in self._sources_name:
                    atomic_ops.append(self._build_step(p_id, i, mid_cmd, [src], [what]))
                else:
                    not_used_sources.append(src)
        else:
            not_used_sources = sources

        # Final aggregation step
        final_step_id = f"{p_id}_{len(atomic_ops) + start_idx}"
        final_op = {
            "id": final_step_id,
            "structured_prompt": {
                "command": final_cmd,
                "from": [op["id"] for op in atomic_ops] + not_used_sources,
                "how": how
            }
        }
        
        return atomic_ops + [final_op]

    def _decompose_summarize(self, mid_cmd: str, sources: list, what: str, 
                            how: dict, p_id: str, start_idx: int) -> List[Dict]:
        """
        Specific decomposition logic for the 'summarize' command.
        """
        ops = self._create_operations(mid_cmd, "integra", sources, what, {}, p_id, start_idx)
        
        # If only one source was extracted, integration is redundant
        if len(ops) == 2:
            ops.pop(-1)

        # Append final summarization step
        summarize_step = self._build_step(
            p_id, start_idx + len(ops), "riassumi", [ops[-1]["id"]], how=how
        )
        ops.append(summarize_step)
        return ops

    def _finalize_integration(self, ops: List[Dict], last_ids: List[str], p_id: str) -> List[Dict]:
        """
        Adds an 'integra' step if multiple 'what' elements were processed.
        """
        if len(last_ids) > 1:
            integration_step = {
                "id": f"{p_id}_{len(ops)}",
                "structured_prompt": {
                    "command": "integra",
                    "from": last_ids
                }
            }
            ops.append(integration_step)
        return ops

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _build_step(self, p_id: str, idx: int, cmd: str, src: list, 
                   what: list = None, how: dict = None) -> Dict:
        """
        Helper to construct a standard operation dictionary.
        """
        prompt = {"command": cmd, "from": src}
        if what: prompt["what"] = what
        if how: prompt["how"] = how
        return {"id": f"{p_id}_{idx}", "structured_prompt": prompt}

    def _find_middle_commands(self, what: str) -> List[str]:
        """
        Finds compatible intermediate commands for a given 'what' parameter.
        """
        if what in ["intero documento", "altro"]:
            return ["cerca"]
        
        for item in self._dql_language.get_what():
            if what == item.get("name", ""):
                relative = item.get("relative_command", [])
                if relative:
                    return relative
                break
        
        default = self._dql_language.default_command.get("command", "cerca")
        return [default]

    def _need_decomposition(self, sources: list, what: str) -> bool:
        """
        Checks if the command needs to be split based on sources or content type.
        """
        has_known_source = any(s in self._sources_name for s in sources)
        return has_known_source or what != "intero documento"