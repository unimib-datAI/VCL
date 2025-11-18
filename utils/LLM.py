import ast
import json
import os
import threading
import time

from copy import deepcopy
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser

from utils.file_manager import FileHandler


class LLM:
    """
    Thread-safe Singleton class for initializing, managing, and invoking
    Large Language Models (LLMs) through LangChain.

    This class provides a unified interface to multiple LLM providers 
    (Gemini, OpenAI, Copilot, HuggingFace) while ensuring that only a single 
    model instance is created across threads. It handles provider-specific 
    API key management, prompt template construction, and controlled invocation
    with a configurable delay between requests.

    Supported providers:
        - google_genai (Gemini)
        - openai (GPT models)
        - copilot (GitHub Copilot API)
        - huggingface (Hugging Face Inference API)

    If initialization with the selected provider fails, the class 
    automatically falls back to Gemini ("gemini-2.0-flash").

    Attributes:
        _model_name (str): The name of the LLM model (e.g., "gpt-4o-mini").
        _provider (str): The provider name ("google_genai", "openai", etc.).
        _llm: The initialized LangChain chat model instance.
        parser (StrOutputParser): Default parser for string-based model responses.
        _seconds (int): Delay (in seconds) between consecutive LLM invocations.
        _project_root (Path): Root directory used to locate API key files.
    """

    # Singleton instance and thread lock
    _instance = None
    _lock = threading.Lock()

    # Default model configuration
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"
    parser = StrOutputParser()

    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(
        self,
        api_key: str = None,
        seconds: int = 5,
        project_root=None,
        model_name: str = "gemini-2.0-flash",
        provider: str = "google_genai",
    ):
        """
        Initialize the LLM instance. (Private, use get_instance())

        Args:
            api_key (str, optional): Provider API key.
            seconds (int): Delay between LLM invocations.
            project_root (Path): Root directory for key files.
            model_name (str): Name of the model to use.
            provider (str): LLM provider ('google_genai', 'openai', 'copilot', 'huggingface').
        """
        self._project_root = project_root

        try:
            self._initialize_llm(api_key, model_name, provider)
        except Exception as e:
            # Fallback to Gemini in case of provider failure
            print(f"Failed to initialize requested LLM ({provider}/{model_name}). Falling back to Gemini. Error: {e}")
            self._initialize_llm(None, "gemini-2.0-flash", "google_genai")

        self._seconds = seconds
        self._initialized = True

    @classmethod
    def get_instance(
        cls,
        api_key: str = None,
        seconds: int = 5,
        project_root=None,
        model_name: str = "gemini-2.0-flash",
        provider: str = "google_genai",
    ):
        """
        Retrieve the singleton instance of the LLM in a thread-safe manner.

        Args:
            api_key (str, optional): Provider API key.
            seconds (int): Delay between LLM invocations.
            project_root (Path): Root directory for key files.
            model_name (str): Name of the model to use.
            provider (str): LLM provider.
        
        Returns:
            LLM: The singleton LLM instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(
                        api_key=api_key,
                        seconds=seconds,
                        project_root=project_root,
                        model_name=model_name,
                        provider=provider,
                    )
        return cls._instance

    # -----------------------
    # --- Private Helpers ---
    # -----------------------

    def _initialize_llm(self, api_key, model_name, provider):
        """
        Initialize the LangChain chat model for the specified provider and model.
        """
        self._model_name = model_name
        self._provider = provider

        # Path for provider-specific API key
        api_path = self._project_root / "settings" / f"api_key_{provider}.txt"

        # Load API key
        api_key = self._load_api_key(api_key, api_path)

        # Set environment variable
        self._set_env_key(provider, api_key)

        # Initialize model
        self._llm = init_chat_model(model_name, model_provider=provider)

    def _set_env_key(self, provider: str, api_key: str):
        """
        Set the correct environment variable for each supported provider.
        """
        env_map = {
            "google_genai": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "copilot": "GITHUB_COPILOT_API_KEY",
            "huggingface": "HUGGINGFACEHUB_API_TOKEN",
        }
        env_name = env_map.get(provider, "")
        if not env_name:
            raise ValueError(f"Unsupported provider: {provider}")
        os.environ[env_name] = api_key

    def _load_api_key(self, api_key: str, api_path) -> str:
        """
        Load the API key from argument or from file. If not present, raise an error.

        Args:
            api_key (str): Provided API key.
            api_path (Path): Path to the API key file.

        Returns:
            str: Valid API key.
            
        Raises:
            ValueError: If no API key is provided and none can be found at api_path.
        """
        # If no key is passed, try to read it from the designated file
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = FileHandler().read_file(api_path)

        # If still no key, it's an error
        if not api_key:
            raise ValueError(f"No API key could be found or loaded. Searched at: {api_path}")

        # (Over)write the key file to ensure it's stored for next time
        FileHandler().write_file(api_path, api_key)
        return api_key

    # ------------------------
    # --- Output Formatter ---
    # ------------------------

    # --- JSON Formatter ---
    
    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Safely extract and parse a dictionary from a string.
        Handles both JSON and Python literal dict formats.

        Args:
            output (str): String containing a JSON or Python dictionary.

        Returns:
            dict: Parsed dictionary or empty dict if parsing fails.
        """
        try:
            # Find the first '{' and last '}'
            output = output[output.index("{"): output.rfind("}") + 1]
            try:
                # Try parsing as JSON (strict)
                return json.loads(output)
            except json.JSONDecodeError:
                # Fallback to parsing as Python literal (more permissive)
                return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            # Return empty if no dict is found or parsing fails
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        """
        Safely extract and parse a list from a string.

        Args:
            output (str): String containing a Python list.

        Returns:
            list: Parsed list or empty list if parsing fails.
        """
        try:
            # Find the first '[' and last ']'
            output = output[output.index("["): output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []
            
    # --- String Formatter ---
    
    def _clean_response(self, result: str, lower: bool) -> str:
        """
        Normalize and clean the raw LLM response.
        Removes common preamble markers (like "result:") and normalizes case.
        
        Args:
            result (str): The raw output from the LLM.
            lower (bool): Whether to convert the result to lowercase.
            
        Returns:
            str: The cleaned string.
        """
        if lower:
            result = result.lower()

        # These markers (some in Italian) are specific to the app's prompts
        for marker in ["risultato:", "risposta:", "result:", "response:"]:
            if marker in result.lower():
                # Find index of marker and strip everything before it
                idx = result.lower().index(marker) + len(marker)
                result = result[idx:]

        result = result.strip()
        # Handle cases where the LLM returns an empty string literal
        return "" if result == "''" else result

    # ----------------------
    # --- LLM Invocation ---
    # ----------------------

    def invoke(self, prompt_info: tuple, info_user: dict, lower: bool = False) -> str | list | dict:
        """
        Invoke the LLM with the given prompt template and input data.

        Args:
            prompt_info (tuple): A tuple containing prompt components:
                (prompt_template, static_params, user_param_keys, parser_type)
            info_user (dict): A dictionary containing user-specific data
                              (e.g., {"query": "...", "context": "..."}).
            lower (bool, optional): Whether to lowercase the final result.

        Returns:
            str | list | dict: The cleaned and parsed LLM response. The
                               type depends on the `parser_type` in prompt_info.
        """
        # Unpack the prompt information tuple
        prompt, params_DQL, params_user, parser_type = prompt_info
        
        # Build the input prompt dictionary
        input_prompt = deepcopy(params_DQL) if params_DQL else {}
        for param_key in params_user:
            # Map keys from info_user (e.g., "query") to the prompt
            input_prompt[param_key] = info_user.get(param_key, "")

        # Create and invoke the LangChain chain
        chain = prompt | self._llm | self.parser
        result = chain.invoke(input_prompt)
        
        # Clean the raw string output
        result = self._clean_response(result, lower)
        
        # Parse the result based on the expected type
        if parser_type == "list":
            result = self.str_in_list(result)
        elif parser_type == "dict":
            result = self.str_in_dict(result)
        # If parser_type is not "list" or "dict", the raw string is returned
        
        # Enforce a delay to avoid rate-limiting
        time.sleep(self._seconds)

        return result