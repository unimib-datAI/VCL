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
    Manages user-specific DQL (Domain Query Language) configurations.

    This class handles loading, caching, updating, and providing access to
    language definitions (commands, sources, 'what' elements) and
    compiled prompt templates. It is instantiated per-user, as
    settings are retrieved from the user's profile in Storage.

    Attributes:
        prompts (dict): A dictionary of compiled LangChain prompt templates,
                        keyed by prompt filename (e.g., "Generator.json").
        gui_examples (list): A list of formatted example query strings,
                             dynamically generated for a GUI.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------
    
    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    def __init__(self, user_id, storage: Storage, project_root):
        """
        Initialize the DQLLanguage instance for a specific user.

        Args:
            user_id (str): The unique identifier for the user.
            storage (Storage): The application's storage (MongoDB) instance.
            project_root (Path): The root directory of the project.
            role (str): The role of the user (Giudice, Avvocato, Altro)
            
        Raises:
            ValueError: If user_id is None.
        """
        if user_id is None:
            raise ValueError("user_id must be provided to initialize DQLLanguage.")
        
        self._user_id = user_id
        self._storage = storage
        self._project_root = project_root
        self._role = "Altro"
        
        # Internal cache for the user's full language definition
        self._full_language: dict | None = None

        # --- Derived attributes (will be populated by _update_parameters) ---
        self._commands: list = []
        self._sources: list = []
        self._what: list = []
        
        self._key_command_map: dict = {}
        self._command_description_map: dict = {}
        self._command_guidelines_map: dict = {}
        self._default_command: dict = {}
        
        self.prompts: dict = {}
        self.gui_examples: list = []

        # Initialize language and all derived properties
        self._update_parameters(to_retrieve=True)
        
        self._initialized = True
        
    @classmethod
    def get_instance(
        cls,
        user_id = None, 
        storage: Storage = None, 
        project_root = None
    ) -> "Storage":
        """
        Retrieve or create the singleton instance of DQLLanguage (thread-safe).

        Args:
            user_id (str): The unique identifier for the user.
            storage (Storage): The application's storage (MongoDB) instance.
            project_root (Path): The root directory of the project.

        Returns:
            Storage: Singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check lock
                if cls._instance is None:
                    cls._instance = cls(user_id, 
                                        storage,
                                        project_root)
        return cls._instance
    
    
    def set_role(self, role):
        self._role = role
        self._update_parameters(to_retrieve=True)
        
    # ---------------------------
    # --- Language Management ---
    # ---------------------------

    def get_language(self) -> dict:
        """
        Retrieve the current language configuration from cache or storage.

        If no language is found in storage for the user, this method
        loads the default language, sets it in storage, and returns it.

        Returns:
            dict: The full language definition.
        """
        if not self._full_language:
            # 1. Try to get from storage
            self._full_language = self._storage.get_language(self._user_id)

            # 2. If not in storage, set to default and get again
            if not self._full_language:
                self._storage.set_default_language(self._user_id)
                self._full_language = self._storage.get_language(self._user_id)
                
                # 3. Failsafe: if storage failed, load from file directly
                if not self._full_language:
                    self._full_language = self._get_default_language_from_file()

        return self._full_language
    
    def get_commands(self) -> list:
        """Returns the list of command definitions."""
        return self._commands
    
    def get_sources(self) -> list:
        """Returns the list of source definitions."""
        return self._sources
    
    def get_what(self) -> list:
        """Returns the list of 'what' definitions."""
        return self._what

    def set_language(self, language: dict) -> bool:
        """
        Set a new language configuration in storage and update
        internal structures.

        Args:
            language (dict): The new language definition.
            
        Returns:
            bool: True if the operation was successful.
        """
        result = self._storage.set_language(self._user_id, language)
        if result:
            # Force refresh of all internal parameters
            self._update_parameters(to_retrieve=True)
        return result
        
    def _get_default_language_from_file(self) -> dict:
        """Helper to load the default language JSON from the file system."""
        default_language_path = os.path.join(
            self._project_root, "documents", "language", "default_language.json"
        )
        return FileHandler().read_file(default_language_path)

    def set_default_language(self) -> bool:
        """
        Load the default language configuration from project files and
        apply it to the current user.
        
        Returns:
            bool: True if the operation was successful.
        """
        default_language = self._get_default_language_from_file()
        return self.set_language(default_language)
        
    def set_commands(self, commands: list) -> bool:
        """
        Update the 'commands' list for the user and refresh parameters.
        
        Returns:
            bool: True if the operation was successful.
        """
        result = self._storage.set_commands(self._user_id, commands)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_sources(self, sources: list) -> bool:
        """
        Update the 'sources' list for the user and refresh parameters.
        
        Returns:
            bool: True if the operation was successful.
        """
        result = self._storage.set_sources(self._user_id, sources)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_what(self, what: list) -> bool:
        """
        Update the 'what' list for the user and refresh parameters.
        
        Returns:
            bool: True if the operation was successful.
        """
        result = self._storage.set_what(self._user_id, what)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    # --------------------------------
    # --- Internal State Refresher ---
    # --------------------------------

    def _update_parameters(self, to_retrieve: bool = False):
        """
        Refresh all internal derived structures (commands, sources, maps,
        prompts) from the loaded language configuration.

        Args:
            to_retrieve (bool): If True, reloads the language from storage
                                first by clearing the local cache.
        """
        if to_retrieve:
            self._full_language = None # Clear cache
        
        # Load language from cache or storage
        self.get_language()

        self._commands = self._full_language.get("commands", [])
        self._sources = self._full_language.get("sources", [])
        self._what = self._full_language.get("what", [])
        
        # Ensure 'what' definitions only refer to existing 'sources'
        self._check_what_coherence()

        # Build internal helper maps
        self._set_default_command()
        self._build_command_maps()
        self._build_what_maps()
        
        # Generate dynamic assets
        self._generate_prompts()
        self.gui_examples = self._generate_gui_examples()

    # --- Command Maps ---
    
    def _build_command_maps(self):
        """
        Build internal dictionaries for fast lookup of command properties.
        - `_key_command_map`: maps shortcut keys (e.g. 'r') -> name (e.g. 'run')
        - `_command_description_map`: maps name -> human-readable description
        - `_command_guidelines_map`: maps name -> formatted guidelines string
        """
        self._key_command_map: dict[str, str] = {}
        self._command_description_map: dict[str, str] = {}
        self._command_guidelines_map: dict[str, str] = {}

        for cmd in self._commands:
            command_name = cmd.get("command", "altro")
            self._key_command_map[cmd.get("key")] = command_name
            self._command_description_map[command_name] = cmd.get("description")
            self._command_guidelines_map[command_name] = "\n".join(cmd.get("guidelines", [])).strip()

    def get_command_from_key(self, key: str) -> str:
        """
        Get the full command name associated with a shortcut key.

        Args:
            key (str): Single-letter command key (e.g., 'r').

        Returns:
            str: The corresponding command name, or "altro" if not found.
        """
        return self._key_command_map.get(key, "altro")

    def get_description_from_command(self, key: str) -> str:
        """
        Retrieve the description for a command, given its name or key.

        Args:
            key (str): Command name or single-letter key.

        Returns:
            str: Description text, or an empty string if not found.
        """
        # If key is a single character, treat it as a shortcut key
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self._command_description_map.get(key, "")
    
    def get_guidelines_from_command(self, key: str) -> str:
        """
        Retrieve the guidelines for a command, given its name or key.

        Args:
            key (str): Command name or single-letter key.

        Returns:
            str: Guidelines text, or an empty string if not found.
        """
        # If key is a single character, treat it as a shortcut key
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self._command_guidelines_map.get(key, "")
    
    # -----------------------
    # --- Default Command ---
    # -----------------------

    def _set_default_command(self):
        """
        Determine and store the default command from the language configuration.
        
        The default is any command marked "default: true" or named "altro".
        If none, it falls back to the last command in the list.
        """
        default_commands = [
            cmd for cmd in self._commands 
            if cmd.get("default", False) or cmd.get("command", "") == "altro"
        ]

        if not default_commands and self._commands:
            # Fallback to the last command
            default_commands = [self._commands[-1]]

        self._default_command = default_commands[0] if default_commands else {}

    @property
    def default_command(self) -> dict:
        """Public accessor for the default command dictionary."""
        return self._default_command
        
    # -------------------------
    # --- "What" Management ---
    # -------------------------
    
    def _build_what_maps(self):
        """
        Build internal dictionaries for fast lookup of what properties.
        - `_what_description_map`: maps name -> human-readable description
        """
        self._what_description_map: dict[str, str] = {}

        for what in self._what:
            self._what_description_map[what.get("name", "")] = what.get("definition")
            
    def get_description_from_what(self, key: str) -> str:
        """
        Retrieve the description for a what element, given its name.

        Args:
            key (str): What name.

        Returns:
            str: Description text, or an empty string if not found.
        """
        return self._what_description_map.get(key, "")

    def get_available_what(self, sources: list[str]) -> dict:
        """
        Retrieve 'what' elements available for a given set of sources.
        
        A 'what' element is available only if the provided sources
        are a subset of the 'what' element's "available" list.

        Args:
            sources (list[str]): List of selected source names.

        Returns:
            dict: Dict of (name, definition) for
                                    available 'what' elements.
        """
        if not sources:
            return {}

        dql_sources = [s.get('name', '') for s in self._sources]
        source_set = set([s for s in sources if s in dql_sources])
        
        what_elements = {}
        
        for item in self._what:
            available = set(item.get("available", []))
            name = item.get("name", "")
            definition = item.get("definition", "")

            # If the sources, after filtering, is empty, we include everything.
            # Otherwise, we check that all the requested sources are available.
            if not source_set or source_set.issubset(available):
                what_elements[name] = definition
                
        return what_elements
    
    def _check_what_coherence(self):
        """
        Ensures 'what' definitions are coherent with 'sources'.
        It filters out any sources listed in a 'what' element's "available"
        list if that source no longer exists in the main 'sources' list.
        If any changes are made, it updates the 'what' definition in storage.
        """
        source_names = [src["name"] for src in self._sources]
        
        new_what_list = []
        is_changed = False
        
        for what in self._what:
            new_what = deepcopy(what)
            available = new_what.get("available", [])
            
            # Filter 'available' to only include sources that actually exist
            coerced_available = [src for src in available if src in source_names]
            
            if coerced_available != available:
                is_changed = True
                new_what["available"] = coerced_available
                
            new_what_list.append(new_what)
        
        # If any 'what' entry was modified, save the entire new list
        if is_changed:
            self.set_what(new_what_list)
            
    # -----------------------------
    # --- "Examples" Management ---
    # -----------------------------
    
    def _generate_gui_examples(self) -> list:
        """
        Loads example prompt templates from a file and dynamically populates
        them with commands, sources, and 'what' elements from the current
        user's language configuration.

        This is used to provide realistic, usable examples to a GUI.
        
        Example template: "Create a [command_riassumi] of [source_S1]"
        Becomes: "Create a summary of S1 - AN"
        
        Returns:
            list: A list of formatted, ready-to-use example strings.
        """
        try:
            examples = FileHandler().read_file(
                os.path.join(
                    self._project_root,
                    "documents",
                    "language",
                    "prompt_examples.json"
                )
            ).get("examples", [])
        except FileNotFoundError:
            return [] # Return empty if no examples file
        
        formatted_examples = []
        
        # Create mapping of available elements
        categories = {
            "command": [cmd["command"] for cmd in self._commands],
            "source": [src["name"] for src in self._sources],
            "what": [w["name"] for w in self._what],
        }

        for e in examples:
            brackets_content = re.findall(r"\[(.*?)\]", e)

            # Count how many placeholders are needed for each category
            needed_counts = {
                "command": sum(1 for c in brackets_content if c.startswith("command_")),
                "source": sum(1 for c in brackets_content if c.startswith("source_")),
                "what": sum(1 for c in brackets_content if c.startswith("what_")),
            }

            # If we don't have enough elements to fill the placeholders, skip
            if any(needed_counts[k] > len(categories[k]) for k in categories):
                continue

            formatted_example = e
            # Keep track of elements used in *this* example to avoid reuse
            used = {k: set() for k in categories}

            # --- Helper to pick a replacement ---
            def choose_replacement(category, element):
                """Returns the value to be inserted, or None if not available."""
                available = categories[category]
                used_set = used[category]

                # 1. Try to use the specific element if valid and unused
                if element in available and element not in used_set:
                    choice = element
                else:
                    # 2. Find the first available one that hasn't been used
                    remaining = [a for a in available if a not in used_set]
                    if not remaining:
                        return None # Not enough unique elements
                    choice = remaining[0]

                used_set.add(choice)
                return choice
            # --- End Helper ---

            # Apply replacements
            valid_example = True
            for content in brackets_content:
                parts = content.split("_", 1)
                if len(parts) != 2:
                    continue # Not a valid placeholder

                category, element = parts
                if category not in categories:
                    valid_example = False # Placeholder for unknown category
                    break

                replacement = choose_replacement(category, element)
                if not replacement:
                    valid_example = False # Not enough elements
                    break

                formatted_example = formatted_example.replace(f"[{content}]", replacement)

            if valid_example:
                formatted_examples.append(formatted_example)

        return formatted_examples
    
    # -----------------------------
    # --- Prompt Generation ---
    # -----------------------------
    
    def _generate_prompts(self):
        """
        Loads all .json prompt templates from the /documents/prompts
        directory, resolves DQL parameters, builds FewShot prompts
        if needed, and stores the compiled prompts in `self.prompts`.
        """
        folder = os.path.join(self._project_root, "documents", "prompts")
        self.prompts = {}
        
        if not os.path.exists(folder):
            return # No prompts to load

        for file in sorted(os.listdir(folder)):
            if not str(file).endswith(".json"):
                continue
            
            try:
                template = FileHandler().read_file(os.path.join(folder, file))
            except Exception:
                continue # Skip corrupted prompt files
            
            system_msg = "\n".join(template.get("system", []))
            human_msg = "\n".join(template.get("human", []))
            examples = template.get("examples", [])
            
            # Resolve static parameters (from DQL language)
            params_DQL = self._resolve_DQL_params(
                template.get("params", {}).get("from_DQL", [])
            )
            
            # Get list of dynamic parameters (from user input)
            params_user = template.get("params", {}).get("from_user", [])
            parser = template.get("parser", "str")
            
            if examples:
                few_shot_prompt = self._build_few_shot_prompt(examples)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_msg),
                    few_shot_prompt,
                    ("human", human_msg),
                ])
            else:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_msg),
                    ("human", human_msg),
                ])
            
            # Store all components needed to invoke the chain
            self.prompts[file] = [prompt, params_DQL, params_user, parser]
        
    def _resolve_DQL_params(self, params: list) -> dict:
        """
        Resolve parameters defined in a prompt's "from_DQL" list.
        This injects dynamic DQL content (like lists of commands/sources)
        into the static prompt templates.

        Args:
            params (list): List of parameter names to resolve
                           (e.g., "key|default", "sources").
        Returns:
            dict: Resolved parameters with their corresponding values.
        """
        resolved = {}
        for param in params:
            if "role" in param:
                resolved[param] = FileHandler().read_file(
                    os.path.join(
                        self._project_root, 
                        "documents", 
                        "prompts", 
                        "header", 
                        f"{self._role}.txt"
                    )
                )
            elif "commands" in param:
                if "|" in param:
                    resolved[param] = str(len(self._commands))
                elif "key" in param:
                    resolved[param] = self.commands_string(self._commands, 'key')
                else:
                    resolved[param] = self.commands_string(self._commands, 'command')
            elif "key" in param:
                if "default" in param:
                    resolved[param] = self._default_command.get("key", "")
                elif "first" in param:
                    resolved[param] = self._commands[0].get("key", "") if self._commands else ""
                elif "last" in param:
                    resolved[param] = self._commands[-1].get("key", "") if self._commands else ""
            elif "sources" in param:
                if "|" in param:
                    resolved[param] = str(len(self._sources))
                else:
                    resolved[param] = self.sources_string(self._sources)
            elif "what" in param:
                if "|" in param:
                    resolved[param] = str(len(self._what))
                    
        return resolved

    def _build_few_shot_prompt(self, examples: list) -> FewShotChatMessagePromptTemplate:
        """
        Construct a few-shot prompt section using given examples.
        
        Note: The original code contained complex, non-functional logic
        for dynamic example generation and filtering. This implementation
        uses the simpler, correct behavior of formatting the static examples
        provided in the prompt's JSON file.

        Args:
            examples (list): A list of example dictionaries from the
                             prompt template file.
        
        Returns:
            FewShotChatMessagePromptTemplate: A LangChain prompt component.
        """
        
        # 1. Format static examples
        formatted_examples = [
            {
                "input": "\n".join(ex["input"]).strip(),
                "reasoning": str(ex["reasoning"]).strip(),
                "output": str(ex["output"]).strip(),
            }
            for ex in examples
        ]
        
        # 2. Define the template for a single example
        example_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template(
                "Reasoning: {reasoning}\nResult: {output}"
            ),
        ])

        # 3. Create the few-shot prompt component
        return FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=formatted_examples,
        )
        
    # -----------------------------
    # --- Static Helper Methods ---
    # -----------------------------
    
    @staticmethod
    def sources_string(sources: list) -> str:
        """
        Generate a formatted string of available sources for LLM input or logging.

        Args:
            sources (list): List of source dictionaries with 'name',
                            'description', and 'synonyms'.

        Returns:
            str: A formatted string listing all available sources and synonyms.
        """
        sources_list = []
        
        for src in sources:
            # Get synonyms for this specific source
            synonyms = [f"'{s.strip()}'" for s in src.get("synonyms", [])]
            
            # Build the parts of the string
            name_part = f'"{src["name"]}"'
            paren_part = f" (o {', '.join(synonyms)})" if synonyms else ""
            desc_part = f': {src["description"]}'
            
            sources_list.append(f'\t\t- {name_part}{paren_part}{desc_part}')

        if sources_list:
            # Add a header
            sources_list = ["\t- \"Legal Documents\": Only the following are available:"] + sources_list

        return "\n".join(sources_list)
    
    @staticmethod
    def commands_string(commands: list, main_key: str = 'key') -> str:
        """
        Generate a formatted string of available commands for logging or display.

        Args:
            commands (list[dict]): List of command dictionaries with 'key'
                                   and 'description'.

        Returns:
            str: A formatted string listing all available commands.
        """
        commands_list = [
            f"- \"{cmd[main_key]}\": {cmd['description']}" for cmd in commands
        ]
        return "\n".join(commands_list)