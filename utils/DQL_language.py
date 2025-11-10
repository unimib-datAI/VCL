import os
import re

from utils.file_manager import FileHandler
from utils.storage import Storage

class DQLLanguage:
    """
    Class for managing language configurations (commands, sources, etc.) in the DQL system.

    Handles loading, updating, and retrieving language definitions, including
    default commands and descriptions.

    Attributes:
        storage: Object responsible for reading/writing language data to persistent storage.
        project_root (Path): Root directory of the project.
        full_language (dict): The complete loaded language definition.
        commands (list): List of available commands.
        sources (list): List of available data sources.
        key_command_map (dict): Maps single-letter command keys to full command names.
        command_description_map (dict): Maps command names to their descriptions.
        default_command (dict): The default command configuration.
    """

    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, user_id, storage: Storage, project_root):
        """
        Initialize the DQLLanguage instance.

        Args:
            storage (Storage): Object providing access to storage
            project_root: Main directory of the project
        """
        if user_id is None:
            raise ValueError("user_id must be provided to initialize DQLLanguage.")
        
        self.user_id = user_id
        self.storage = storage
        self.project_root = project_root
        self.full_language: dict | None = None

        # Initialize language and derived properties
        self._update_parameters(to_retrieve=True)

    # ---------------------------
    # --- Language Management ---
    # ---------------------------

    def get_language(self) -> dict:
        """
        Retrieve the current language configuration from storage.

        Returns:
            dict: The full language definition.
        """
        if not self.full_language:
            self.full_language = self.storage.get_language(self.user_id)

            # If not found, fall back to the default language file
            if not self.full_language:
                self.full_language = self.storage.set_default_language(self.user_id)

        return self.full_language
    
    def get_commands(self):
        return self.commands
    
    def get_sources(self):
        return self.sources
    
    def get_what(self):
        return self.what

    def set_language(self, language: dict):
        """
        Set a new language configuration and update internal structures.

        Args:
            language (dict): The new language definition.
        """
        result = self.storage.set_language(self.user_id, language)
        if result:
            self._update_parameters(to_retrieve=True)
        
        return result

    def set_default_language(self):
        """
        Load and apply the default language configuration from the project files.
        """
        default_language_path = os.path.join(
            self.project_root, "documents", "language", "default_language.json"
        )
        default_language = FileHandler().read_file(default_language_path)
        return self.set_language(default_language)
        
    def set_commands(self, commands: list):
        result = self.storage.set_commands(self.user_id, commands)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_sources(self, sources: list):
        result = self.storage.set_sources(self.user_id, sources)
        if result:
            self._update_parameters(to_retrieve=True)
        return result
    
    def set_what(self, what: list):
        result = self.storage.set_what(self.user_id, what)
        
        if result:
            self._update_parameters(to_retrieve=True)
        return result

    def _update_parameters(self, to_retrieve: bool = False):
        """
        Refresh internal structures (commands, sources, maps) from the loaded language.

        Args:
            to_retrieve (bool): If True, reloads the language from storage first.
        """
        if to_retrieve:
            self.full_language = self.storage.get_language(self.user_id)

        self.commands = self.full_language.get("commands", [])
        self.sources = self.full_language.get("sources", [])
        self.what = self.full_language.get("what", [])

        self._set_default_command()
        self._build_command_maps()
        
        self.gui_examples = self._generate_gui_examples()

    # --------------------------
    # --- Command Management ---
    # --------------------------

    def _build_command_maps(self):
        """
        Build internal dictionaries mapping command keys and descriptions.

        - `key_command_map`: maps shortcut keys (e.g. 'r') → command name (e.g. 'run')
        - `command_description_map`: maps command name → human-readable description
        """
        self.key_command_map: dict[str, str] = {}
        self.command_description_map: dict[str, str] = {}
        self.command_guidelines_map: dict[str, str] = {}

        for cmd in self.full_language.get("commands", []):
            self.key_command_map[cmd["key"]] = cmd["command"]
            self.command_description_map[cmd["command"]] = cmd["description"]
            self.command_guidelines_map[cmd["command"]] = "\n".join(cmd["guidelines"]).strip()

    def get_command_from_key(self, key: str) -> str:
        """
        Get the full command name associated with a shortcut key.

        Args:
            key (str): Single-letter command key (e.g., 'r').

        Returns:
            str: The corresponding command name, or "altro" if not found.
        """
        return self.key_command_map.get(key, "altro")

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
        return self.command_description_map.get(key, "")
    
    def get_guidelines_from_command(self, key: str) -> str:
        """
        Retrieve the guidelines for a command, given its name or key.

        Args:
            key (str): Command name or single-letter key.

        Returns:
            str: Description text, or an empty string if not found.
        """
        # If key is a single character, treat it as a shortcut key
        if len(key) == 1:
            key = self.get_command_from_key(key)
        return self.command_guidelines_map.get(key, "")

    def _set_default_command(self):
        """
        Determine and store the default command from the language configuration.

        If no command is explicitly marked as default, the last command in the list is used.
        """
        default_commands = [cmd for cmd in self.commands if cmd.get("default", False)]

        if not default_commands and self.commands:
            default_commands = [self.commands[-1]]

        self.default_command = default_commands[0] if default_commands else {}

    # -------------------------
    # --- "What" Management ---
    # -------------------------

    def get_available_what(self, sources: list[str]) -> list[tuple[str, str]]:
        """
        Retrieve 'what' elements available for a given set of sources.

        Args:
            sources (list[str]): List of selected sources.

        Returns:
            list[tuple[str, str]]: Tuples of (name, definition) for available 'what' elements.
        """
        if not sources:
            return []

        what_elements = [
            (what.get("name", ""), what.get("definition", ""))
            for what in self.full_language.get("what", [])
            if set(sources).issubset(what.get("available", []))
        ]
        return what_elements
    
    # -----------------------------
    # --- "Examples" Management ---
    # -----------------------------
    
    def _generate_gui_examples(self):
        examples = FileHandler().read_file(
            os.path.join(
                self.project_root,
                "documents",
                "language",
                "prompt_examples.json"
            )
        ).get("examples", [])
        
        formatted_examples = []
        
        categories = {
            "command": [cmd["command"] for cmd in self.commands],
            "source": [src["name"] for src in self.sources],
            "what": [w["name"] for w in self.what],
        }

        for e in examples:
            brackets_content = re.findall(r"\[(.*?)\]", e)

            # Count how many placeholders you need for each category
            needed_counts = {
                "command": sum(1 for c in brackets_content if c.startswith("command_")),
                "source": sum(1 for c in brackets_content if c.startswith("source_")),
                "what": sum(1 for c in brackets_content if c.startswith("what_")),
            }

            # If enough elements are missing, discard
            if any(needed_counts[k] > len(categories[k]) for k in categories):
                continue

            formatted_example = e
            used = {k: set() for k in categories}

            # ------------------------------------------
            
            def choose_replacement(category, element):
                """Returns the value to be inserted, or None if not available."""
                available = categories[category]
                used_set = used[category]

                # Priority to the specified one if valid and unused
                if element in available and element not in used_set:
                    choice = element
                else:
                    # Find the first available one that hasn't been used yet
                    remaining = [a for a in available if a not in used_set]
                    if not remaining:
                        return None
                    choice = remaining[0]

                used_set.add(choice)
                return choice
            
            # ------------------------------------------

            # Apply replacements
            for content in brackets_content:
                parts = content.split("_", 1)
                if len(parts) != 2:
                    continue

                category, element = parts
                if category not in categories:
                    formatted_example = None
                    break

                replacement = choose_replacement(category, element)
                if not replacement:
                    formatted_example = None
                    break

                formatted_example = formatted_example.replace(f"[{content}]", replacement)

            if formatted_example:
                formatted_examples.append(formatted_example)

        return formatted_examples
