import os
import re
import threading
from copy import deepcopy

from utils.file_manager import FileHandler
from utils.storage import Storage

from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)

class DQLLanguage:
    """
    Orchestrates the Domain Query Language (DQL) specifications and LLM prompts.

    This class serves as a dynamic bridge between stored user configurations and 
    LLM prompt engineering. It manages the lifecycle of DQL components (commands, 
    sources, 'what' elements) and compiles them into LangChain-compatible 
    templates tailored to the user's role and session history.

    Key Features:
        - Dynamic prompt compilation from JSON templates.
        - User role-based content injection (Judge vs. Lawyer headers).
        - Integrated Few-Shot example management.
        - Grammar coherence validation between sources and targets.
    """
    
    # Singleton pattern infrastructure
    _instance = None
    _lock = threading.Lock()

    def __init__(self, user_id: str, storage: Storage, project_root: str):
        """
        Initialize a user-specific DQL Language context.

        Args:
            user_id (str): Unique identifier for the authenticated user.
            storage (Storage): Backend service handle for database operations.
            project_root (str): Absolute path to the project root directory.
        
        Raises:
            ValueError: If user_id is not provided.
        """
        if user_id is None:
            raise ValueError("user_id must be provided to initialize DQLLanguage.")
        
        self._user_id = user_id
        self._storage = storage
        self._project_root = project_root
        self._role = "Altro" # Default fallback role
        
        # Centralized language cache
        self._full_language: dict | None = None

        # --- Pipeline Parameters ---
        self._commands: list = []
        self._sources: list = []
        self._what: list = []
        
        # Optimization maps for fast metadata retrieval
        self._key_command_map: dict = {}
        self._command_description_map: dict = {}
        self._command_guidelines_map: dict = {}
        self._default_command: dict = {}
        
        # Compiled LangChain prompt objects
        self.prompts: dict = {}
        
        # Dynamic suggestions for the user interface
        self.gui_examples: list = []

        # Bootstrapping: Load grammar and compile initial prompts
        self._update_parameters(to_retrieve=True)
        self._initialized = True
        
    @classmethod
    def get_instance(cls, user_id=None, storage: Storage=None, project_root=None) -> "DQLLanguage":
        """
        Thread-safe singleton accessor for the DQLLanguage engine.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(user_id, storage, project_root)
        return cls._instance
    
    def set_role(self, role: str):
        """
        Updates the functional role of the session and triggers a prompt recompilation
        to ensure context-aware persona behaviors.
        """
        self._role = role
        self._update_parameters(to_retrieve=True)
        
    # ---------------------------
    # --- Language Management ---
    # ---------------------------

    def get_language(self) -> dict:
        """
        Retrieves the complete user-specific DQL grammar.
        Falls back to the system default if no database record is found.
        """
        if not self._full_language:
            # Attempt to fetch persistent user settings
            self._full_language = self._storage.get_language(self._user_id)

            if not self._full_language:
                # Initialize new user with default grammar
                self._storage.set_default_language(self._user_id)
                self._full_language = self._storage.get_language(self._user_id)
                
                # Failsafe: direct disk read if DB is unreachable/corrupted
                if not self._full_language:
                    self._full_language = self._get_default_language_from_file()

        return self._full_language
    
    # Grammar accessors
    def get_commands(self) -> list: return self._commands
    def get_sources(self) -> list: return self._sources
    def get_what(self) -> list: return self._what

    def set_language(self, language: dict) -> bool:
        """
        Updates the global language definition and invalidates caches for recompilation.
        """
        result = self._storage.set_language(self._user_id, language)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
        
    def _get_default_language_from_file(self) -> dict:
        """Internal helper to load the base JSON grammar from static assets."""
        return self._storage._get_default_language(self._user_id)

    def set_default_language(self) -> bool:
        """Restores the user grammar to system defaults."""
        default_language = self._get_default_language_from_file()
        return self.set_language(default_language)
        
    def set_commands(self, commands: list) -> bool:
        """Updates the command set (Intents)."""
        result = self._storage.set_commands(self._user_id, commands)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_sources(self, sources: list) -> bool:
        """Updates the document source definitions (Scope)."""
        result = self._storage.set_sources(self._user_id, sources)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_what(self, what: list) -> bool:
        """Updates the 'what' elements (Target entities)."""
        result = self._storage.set_what(self._user_id, what)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    # --------------------------------
    # --- Internal State Refresher ---
    # --------------------------------

    def _update_parameters(self, to_retrieve: bool = False):
        """
        Orchestrates the synchronization between the JSON grammar and internal logic.
        This method rebuilds all maps, ensures cross-source coherence, and
        compiles LangChain prompts for the LLM pipeline.
        """
        if to_retrieve:
            self._full_language = None # Invalidate cache
        
        self.get_language()

        self._commands = self._full_language.get("commands", [])
        self._sources = self._full_language.get("sources", [])
        self._what = self._full_language.get("what", [])
        
        # Validation Phase: Prune orphaned sources in entity definitions
        self._check_what_coherence()

        # Build Look-up Phase
        self._set_default_command()
        self._build_command_maps()
        self._build_what_maps()
        
        # Compilation Phase: Generate executable LangChain templates
        self._generate_prompts()
        self.gui_examples = self._generate_gui_examples()

    # --- Mapping Utilities ---
    
    def _build_command_maps(self):
        """Populates dictionaries for O(1) retrieval of command metadata."""
        self._key_command_map = {}
        self._command_description_map = {}
        self._command_guidelines_map = {}

        for cmd in self._commands:
            command_name = cmd.get("command", "altro")
            self._key_command_map[cmd.get("key")] = command_name
            self._command_description_map[command_name] = cmd.get("description", "")
            self._command_guidelines_map[command_name] = "\n".join(cmd.get("guidelines", [])).strip()

    def get_command_from_key(self, key: str) -> str:
        """Maps single-character shortcuts to full DQL command strings."""
        return self._key_command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        """Resolves the functional description for a given command/key."""
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self._command_description_map.get(key, "")
    
    def get_guidelines_from_command(self, key: str) -> str:
        """Resolves specific prompt guidelines for the provided command."""
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self._command_guidelines_map.get(key, "")
    
    def _set_default_command(self):
        """Identifies the 'catch-all' intent from the current configuration."""
        default_commands = [
            cmd for cmd in self._commands 
            if cmd.get("default", False) or cmd.get("command", "") == "altro"
        ]
        # Safety fallback: uses the penultimate command (excluding 'riformula')
        if not default_commands and self._commands:
            default_commands = [self._commands[-1]]

        self._default_command = default_commands[0] if default_commands else {}

    @property
    def default_command(self) -> dict: return self._default_command
        
    def _build_what_maps(self):
        """Builds lookup for entity definitions."""
        self._what_description_map = {}
        for item in self._what:
            self._what_description_map[item.get("name", "")] = item.get("definition")
            
    def get_description_from_what(self, key: str) -> str:
        """Resolves entity definition based on target name."""
        if key == "intero documento":
            return "l'utente vuole operare considerando il documento nella sua interezza"
        
        if key == "frase":
            return "l'utente vuole estrarre una frase simile o relativa a un elemento nella richiesta, tendenzialmente tra \"\""
        
        if key == "concetto":
            return "l'utente vuole individuare l'occorrenza di una stringa e il significato nel testo."
        
        return self._what_description_map.get(key, "")

    def get_available_what(self, sources: list[str]) -> dict:
        """
        Filters 'what' targets based on provided document context.
        Logic: All requested sources must be present in the target's 'available' whitelist.
        """
        if not sources:
            return {}

        dql_sources = [s.get('name', '') for s in self._sources]
        source_set = set([s for s in sources if s in dql_sources])
        what_elements = {}
        
        for item in self._what:
            available = set(item.get("available", []))
            if not source_set or source_set.issubset(available):
                what_elements[item.get("name", "")] = item.get("definition", "")
                
        return what_elements
    
    def _check_what_coherence(self):
        """Consistency check: Ensures entity definitions don't reference deleted sources."""
        source_names = [src["name"] for src in self._sources]
        new_what_list = []
        is_changed = False
        
        for what in self._what:
            new_what = deepcopy(what)
            available = new_what.get("available", [])
            coerced_available = [src for src in available if src in source_names]
            
            if coerced_available != available:
                is_changed = True
                new_what["available"] = coerced_available
            new_what_list.append(new_what)
        
        if is_changed:
            self.set_what(new_what_list)
            
    # -----------------------------
    # --- Example Management ---
    # -----------------------------
    
    def _generate_gui_examples(self) -> list:
        """
        Compiles human-readable examples for the UI by injecting current 
        grammar elements into placeholder templates.
        """
        try:
            path = os.path.join(self._project_root, "documents", "language", "prompt_examples.json")
            examples = FileHandler().read_file(path).get("examples", [])
        except FileNotFoundError:
            return []
        
        formatted_examples = []
        categories = {
            "command": [cmd["command"] for cmd in self._commands],
            "source": [src["name"] for src in self._sources],
            "what": [w["name"] for w in self._what],
        }

        for e in examples:
            brackets_content = re.findall(r"\[(.*?)\]", e)
            formatted_example = e
            used = {k: set() for k in categories}

            # Local helper for non-repeating placeholder replacement
            def choose_replacement(category, element):
                available = categories[category]
                used_set = used[category]
                if element in available and element not in used_set:
                    choice = element
                else:
                    remaining = [a for a in available if a not in used_set]
                    if not remaining: return None
                    choice = remaining[0]
                used_set.add(choice)
                return choice

            valid = True
            for content in brackets_content:
                parts = content.split("_", 1)
                if len(parts) != 2: continue
                category, element = parts
                replacement = choose_replacement(category, element)
                if not replacement:
                    valid = False; break
                formatted_example = formatted_example.replace(f"[{content}]", replacement)

            if valid: formatted_examples.append(formatted_example)
        return formatted_examples
    
    # -----------------------------
    # --- Prompt Compilation ---
    # -----------------------------
    
    def _generate_prompts(self):
        """
        Compiles LangChain ChatPromptTemplate objects for every tool and component.
        Resolves role-based headers and few-shot sections during construction.
        """
        folder = os.path.join(self._project_root, "documents", "prompts")
        self.prompts = {}
        
        if not os.path.exists(folder): return

        for file in sorted(os.listdir(folder)):
            if not str(file).endswith(".json"): continue
            
            try:
                template = FileHandler().read_file(os.path.join(folder, file))
            except Exception: continue
            
            # Extract basic structural elements
            system_msg = "\n".join(template.get("system", []))
            human_msg = "\n".join(template.get("human", []))
            examples = template.get("examples", [])
            
            # Resolve grammar-driven static parameters (e.g. lists of commands)
            params_DQL = self._resolve_DQL_params(template.get("params", {}).get("from_DQL", []))
            params_user = template.get("params", {}).get("from_user", [])
            parser = template.get("parser", "str")
            
            # Construct complex chat templates with optional few-shot components
            messages = [("system", system_msg)]
            if examples:
                messages.append(self._build_few_shot_prompt(examples))
            messages.append(("human", human_msg))
            
            self.prompts[file] = [ChatPromptTemplate.from_messages(messages), params_DQL, params_user, parser]
        
    def _resolve_DQL_params(self, params: list) -> dict:
        """Injects system-level metadata (roles, grammar lists) into prompt variables."""
        resolved = {}
        for param in params:
            if "role" in param:
                # Load specialized header based on user functional role
                header_folder = os.path.join(self._project_root, "documents", "prompts", "header")
                role_file = f"{self._role}.txt" if self._role in ["Giudice", "Avvocato"] else "Altro.txt"
                resolved[param] = FileHandler().read_file(os.path.join(header_folder, role_file))
            elif "commands" in param:
                if "key" in param:
                    resolved[param] = self.commands_string(self._commands, 'key')
                else:
                    resolved[param] = str(len(self._commands)) if "|" in param else self.commands_string(self._commands, 'command')
            elif "key" in param:
                if "default" in param: 
                    resolved[param] = self._default_command.get("key", "")
                elif "last" in param: 
                    resolved[param] = self._commands[-1].get("key", "") if len(self._commands) > 0 else ""
                elif "first" in param: 
                    resolved[param] = self._commands[0].get("key", "") if len(self._commands) > 0 else ""
            elif "sources" in param:
                resolved[param] = str(len(self._sources)) if "|" in param else self.sources_string(self._sources)
            elif "what" in param:
                resolved[param] = [f"- \"{item.get('name')}\": {item.get('definition', '')}" for item in self._what]
        return resolved

    def _build_few_shot_prompt(self, examples: list) -> FewShotChatMessagePromptTemplate:
        """Encapsulates few-shot examples into a structured prompt component."""
        formatted_examples = [
            {
                "input": "\n".join(ex["input"]).strip() if isinstance(ex["input"], list) else str(ex["input"]).strip(),
                "reasoning": str(ex.get("reasoning", "")).strip(),
                "output": str(ex["output"]).strip(),
            } for ex in examples
        ]
        example_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("Reasoning: {reasoning}\nResult: {output}"),
        ])
        return FewShotChatMessagePromptTemplate(example_prompt=example_prompt, examples=formatted_examples)
        
    @staticmethod
    def sources_string(sources: list) -> str:
        """Renders document sources as a bulleted technical list for LLM context."""
        sources_list = []
        for src in sources:
            synonyms = [f"'{s.strip()}'" for s in src.get("synonyms", [])]
            label = f'\"{src["name"]}\"' + (f" (o {', '.join(synonyms)})" if synonyms else "")
            label = f'{label}: {src["description"]}'.strip()
            if label.endswith(":"):
                label = label[:-1]
            sources_list.append(f'\t- {label}')
        return "\n".join(sources_list)
    
    @staticmethod
    def commands_string(commands: list, main_key: str = 'key') -> str:
        """Renders command intents as a bulleted list for LLM context."""
        return "\n".join([f"- \"{cmd[main_key]}\": {cmd['description']}" for cmd in commands])