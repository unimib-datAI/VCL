import ast
import json
import os
import threading
import time

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)

from utils.file_manager import FileHandler


class LLM:
    """
    Thread-safe Singleton class for initializing, managing, and invoking
    Large Language Models (LLMs) through LangChain.

    This class provides a unified interface to multiple LLM providers 
    (Gemini, OpenAI, Copilot, HuggingFace) while ensuring that only a single 
    model instance is created across threads. It handles provider-specific 
    API key management, prompt template construction, and controlled invocation
    with configurable delay between requests.

    Supported providers:
        - google_genai (Gemini)
        - openai (GPT models)
        - copilot (GitHub Copilot API)
        - huggingface (Hugging Face Inference API)

    If initialization with the selected provider fails, the class 
    automatically falls back to Gemini ("gemini-2.0-flash").

    Attributes:
        model_name (str): The name of the LLM model (e.g., "gpt-4o-mini", "gemini-2.0-flash").
        provider (str): The provider name ("google_genai", "openai", "copilot", "huggingface").
        llm: The initialized LangChain chat model instance.
        parser (StrOutputParser): Default parser for string-based model responses.
        seconds (int): Delay (in seconds) between consecutive LLM invocations.
        project_root (Path): Root directory used to locate API key files.
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
        Initialize the LLM instance.

        Args:
            api_key (str, optional): Provider API key.
            seconds (int): Delay between LLM invocations.
            project_root (Path): Root directory for key files.
            model_name (str): Name of the model to use.
            provider (str): LLM provider ('google_genai', 'openai', 'copilot', 'huggingface').
        """
        self.project_root = project_root

        try:
            self._initialize_llm(api_key, model_name, provider)
        except Exception as e:
            # Fallback to Gemini in case of provider failure
            print(f"Default LLM: {e}")
            self._initialize_llm(None, "gemini-2.0-flash", "google_genai")

        self.seconds = seconds
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
        self.model_name = model_name
        self.provider = provider

        # Path for provider-specific API key
        api_path = self.project_root / "settings" / f"api_key_{provider}.txt"

        # Load API key
        api_key = self._load_api_key(api_key, api_path)

        # Set environment variable
        self._set_env_key(provider, api_key)

        # Initialize model
        self.llm = init_chat_model(model_name, model_provider=provider)

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
        """
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = FileHandler().read_file(api_path)

        if not api_key:
            raise ValueError("No API key could be found or loaded.")

        FileHandler().write_file(api_path, api_key)
        return api_key

    # --------------------
    # --- JSON Parsers ---
    # --------------------

    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Safely extract and parse a dictionary from a string.

        Args:
            output (str): String containing a JSON or Python dictionary.

        Returns:
            dict: Parsed dictionary or empty dict if parsing fails.
        """
        try:
            output = output[output.index("{"): output.rfind("}") + 1]
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return ast.literal_eval(output)
        except (ValueError, SyntaxError):
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
            output = output[output.index("["): output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []

    # ---------------------------
    # --- Prompt Construction ---
    # ---------------------------

    def build_from_file(self, file_name: str, inputs: dict) -> ChatPromptTemplate:
        """
        Build a LangChain ChatPromptTemplate from a structured JSON file.

        Args:
            file_name (str): Path to the JSON prompt template file.
            inputs (dict): Input values to fill template parameters.

        Returns:
            tuple[ChatPromptTemplate, dict]: The constructed prompt template and input map.
        """
        template = FileHandler().read_file(file_name)

        system_msg = "\n".join(template.get("system", []))
        human_msg = "\n".join(template.get("human", []))
        params = template.get("params", [])
        examples = template.get("examples", [])

        input_template = self._resolve_template_params(params, inputs)

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

        return prompt, input_template

    def _resolve_template_params(self, params, inputs) -> dict:
        """
        Resolve template parameters from user-provided inputs.
        """
        input_template = {}
        for p in params:
            if isinstance(p, list) and len(p) == 2:
                input_template["_".join(p)] = str(inputs[p[0]][p[1]])
            elif isinstance(p, str):
                input_template[p] = str(inputs[p])
        return input_template

    def _build_few_shot_prompt(self, examples: list) -> FewShotChatMessagePromptTemplate:
        """
        Construct a few-shot prompt section using given examples.
        """
        formatted_examples = [
            {
                "input": "\n".join(ex["input"]).strip(),
                "reasoning": ex["reasoning"],
                "output": str(ex["output"]),
            }
            for ex in examples
        ]

        example_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template(
                "Reasoning: {reasoning}\nResult: {output}"
            ),
        ])

        return FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=formatted_examples,
        )

    # ----------------------
    # --- LLM Invocation ---
    # ----------------------

    def invoke(self, file_name: str, input_state: dict, lower: bool = False) -> str:
        """
        Invoke the LLM with the given prompt template and input data.

        Args:
            file_name (str): Path to the prompt template file.
            input_state (dict): Data for filling in prompt placeholders.
            lower (bool): Whether to convert the output to lowercase.

        Returns:
            str: Cleaned LLM response text.
        """
        prompt, input_prompt = self.build_from_file(file_name, input_state)
        chain = prompt | self.llm | self.parser
        result = chain.invoke(input_prompt)
        time.sleep(self.seconds)

        return self._clean_response(result, lower)

    def _clean_response(self, result: str, lower: bool) -> str:
        """
        Normalize and clean the raw LLM response.
        """
        if lower:
            result = result.lower()

        for marker in ["risultato:", "risposta:", "result:", "response:"]:
            if marker in result.lower():
                idx = result.lower().index(marker) + len(marker)
                result = result[idx:]

        result = result.strip()
        return "" if result == "''" else result
