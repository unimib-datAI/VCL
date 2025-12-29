import ast
import json
import os
import threading
import time

from copy import deepcopy
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser

class LLM:
    """
    Thread-safe Singleton class for managing Large Language Models via LangChain.

    This class provides a unified abstraction layer over multiple LLM providers, 
    ensuring that only one model instance exists per execution context. It handles 
    automatic fallback to Gemini if the primary provider fails and enforces 
    rate-limiting through configurable delays.

    Responsibilities:
        - Abstracting provider-specific logic (OpenAI, Gemini, Copilot, HF).
        - Managing environment variables for API authentication.
        - Parsing diverse LLM output formats (JSON, Python literals, Markdown).
        - Ensuring thread safety during initialization using a global lock.
    """
    
    # Load environmental variables from .env on class definition
    load_dotenv()
    
    # Static variables for Singleton management
    _instance = None
    _lock = threading.Lock()

    # Default settings
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"
    parser = StrOutputParser()

    # Mapping of logical provider names to their respective environment keys
    _PROVIDER_ENV_MAP = {
        "google_genai": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "copilot": "GITHUB_COPILOT_API_KEY",
        "huggingface": "HUGGINGFACEHUB_API_TOKEN",
    }

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
        Private constructor to set up the LLM engine.

        Args:
            api_key (str, optional): Key for API access. Defaults to env lookup.
            seconds (int): Pause duration between invocations to prevent rate-limiting.
            project_root (Path): Root project directory for path resolution.
            model_name (str): Specific model ID (e.g., 'gpt-4o-mini').
            provider (str): Provider key (e.g., 'openai').
        """
        self._project_root = project_root

        try:
            # Primary attempt: Initialize with user preferences
            self._initialize_llm(api_key, model_name, provider)
        except Exception as e:
            # Secondary attempt: Automatic fallback to highly available Gemini engine
            print(f"CRITICAL: Failed to initialize {provider}/{model_name}. Fallback triggered. Error: {e}")
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
        Thread-safe accessor for the Singleton instance.

        Uses the Double-Checked Locking pattern to minimize overhead 
        while ensuring safe concurrent access during the first creation.

        Returns:
            LLM: The shared engine instance.
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

    def _initialize_llm(self, api_key: str, model_name: str, provider: str):
        """
        Constructs the LangChain chat model after verifying authentication.
        """
        self._model_name = model_name
        self._provider = provider

        # Retrieve and sanitize the API key
        api_key = self._load_api_key(api_key, provider)

        # Inject key into os.environ for LangChain standard compatibility
        self._set_env_key(provider, api_key)

        # Initialize the dynamic LangChain chat model wrapper
        self._llm = init_chat_model(model_name, model_provider=provider)

    def _set_env_key(self, provider: str, api_key: str):
        """
        Updates process-level environment variables for the selected provider.
        """
        env_name = self._PROVIDER_ENV_MAP.get(provider, "")
        if not env_name:
            raise ValueError(f"Integration error: Unsupported provider '{provider}'")
        os.environ[env_name] = api_key

    def _load_api_key(self, api_key: str, provider: str) -> str:
        """
        Resolves API credentials from either function arguments or system environment.

        Args:
            api_key (str): Direct key input.
            provider (str): Provider identifier to map to env keys.

        Returns:
            str: Verified API token.
        """
        # Priority 1: Explicitly provided key
        if api_key:
            return api_key

        # Priority 2: Environmental variable lookup
        env_var_name = self._PROVIDER_ENV_MAP.get(provider)
        if not env_var_name:
            raise ValueError(f"Configuration error: Provider '{provider}' has no environment mapping.")

        fetched_key = os.getenv(env_var_name)

        if not fetched_key:
            raise ValueError(f"Auth error: No key found in {env_var_name}. Check your .env file.")

        return fetched_key

    # ------------------------
    # --- Output Formatter ---
    # ------------------------

    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Extracts a dictionary structure from raw LLM text using mixed parsing strategies.
        
        Attempts standard JSON decoding first, falling back to Python Abstract Syntax 
        Tree (AST) evaluation for non-strict JSON formatted outputs.
        """
        try:
            # Semantic extraction: isolate content within the outermost curly braces
            output = output[output.index("{"): output.rfind("}") + 1]
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                # Periphery parser for LLM outputs that use Python syntax (single quotes, etc.)
                return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        """
        Safely extracts a list structure from a string using AST literal evaluation.
        """
        try:
            # Isolate content within square brackets
            output = output[output.index("["): output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []
            
    def _clean_response(self, result: str, lower: bool) -> str:
        """
        Performs post-generation cleanup to remove boilerplate markers and whitespace.
        
        Args:
            result (str): Raw string from LLM.
            lower (bool): Flag to force lowercase output.
        """
        if lower:
            result = result.lower()

        # Remove domain-specific prefixes added by some instruction-tuned models
        prefixes = ["risultato:", "risposta:", "result:", "response:"]
        for marker in prefixes:
            if marker in result.lower():
                idx = result.lower().index(marker) + len(marker)
                result = result[idx:]

        result = result.strip()
        # Handle empty string representations
        return "" if result == "''" else result

    # ----------------------
    # --- LLM Invocation ---
    # ----------------------

    def invoke(self, prompt_info: tuple, info_user: dict, lower: bool = False) -> str | list | dict:
        """
        Coordinates the full LangChain chain execution: Prompt -> LLM -> Parser.

        This method merges static DQL parameters with dynamic user-provided data, 
        invokes the pipeline, and applies the requested formatting logic.

        Args:
            prompt_info (tuple): (ChatPromptTemplate, DQL_params, user_keys, output_type).
            info_user (dict): User context data (e.g. queries, retrieved documents).
            lower (bool): True to lowercase the final response string.

        Returns:
            The parsed response (dict, list, or str) based on the prompt definition.
        """
        # Unpack structural metadata from the prompt loader
        prompt, params_DQL, params_user, parser_type = prompt_info
        
        # Assemble variables: combine system-level DQL context with user interaction data
        input_prompt = deepcopy(params_DQL) if params_DQL else {}
        for param_key in params_user:
            input_prompt[param_key] = info_user.get(param_key, "")

        # LangChain Expression Language (LCEL) chain orchestration
        chain = prompt | self._llm | self.parser
        raw_result = chain.invoke(input_prompt)
        
        # Cleanup and dynamic parsing based on the expected 'parser_type'
        cleaned_result = self._clean_response(raw_result, lower)
        
        if parser_type == "list":
            final_output = self.str_in_list(cleaned_result)
        elif parser_type == "dict":
            final_output = self.str_in_dict(cleaned_result)
        else:
            final_output = cleaned_result
        
        # Throttle execution to comply with provider API rate limits
        time.sleep(self._seconds)

        return final_output