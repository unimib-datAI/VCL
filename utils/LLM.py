import ast
import json
import os
import threading
import time

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
)
from langchain.prompts.chat import (
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)

from utils.file_manager import FileHandler


class LLM:
    """
    Singleton class for initializing, managing, and invoking a Large Language Model (LLM).

    This class ensures that only one instance of the model is created across threads,
    while handling API key management, prompt template building, and invocation routines.

    Attributes:
        model_name (str): Default LLM model name.
        provider (str): LLM provider (e.g., Google GenAI).
        llm: Initialized LangChain chat model instance.
        parser (StrOutputParser): Default output parser for model responses.
        seconds (int): Delay (in seconds) between LLM invocations.
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

    def __init__(self, api_key: str = None, seconds: int = 5, project_root=None):
        """
        Initialize the LLM instance.

        Args:
            api_key (str, optional): API key for the provider. If not provided,
                the class attempts to read it from 'settings/api_key.txt'.
            seconds (int): Delay between LLM invocations.
            project_root (Path): Root project directory, used to locate settings.

        Raises:
            ValueError: If no API key can be found or provided.
        """
        api_path = project_root / "settings" / "api_key.txt"

        # Retrieve or load the API key
        api_key = self._load_api_key(api_key, api_path)
        os.environ["GOOGLE_API_KEY"] = api_key

        # Initialize LangChain chat model
        self.llm = init_chat_model(self.model_name, model_provider=self.provider)
        self.seconds = seconds
        self._initialized = True

    @classmethod
    def get_instance(cls, api_key: str = None, seconds: int = 5, project_root=None):
        """
        Retrieve the singleton instance of the LLM (thread-safe).

        Args:
            api_key (str, optional): API key for initialization.
            seconds (int): Delay between LLM calls.
            project_root (Path): Root project directory.

        Returns:
            LLM: The singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(api_key, seconds, project_root)
        return cls._instance

    # -----------------------
    # --- Private Helpers ---
    # -----------------------

    def _load_api_key(self, api_key: str, api_path) -> str:
        """
        Load API key from argument or from file; save if needed.

        Args:
            api_key (str): Provided API key.
            api_path (Path): Path to API key file.

        Returns:
            str: Valid API key.

        Raises:
            ValueError: If key is not found anywhere.
        """
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = FileHandler().read_file(api_path)

        if not api_key:
            raise ValueError("No API key could be found or loaded.")

        # Persist the key (could normalize or update formatting)
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
            # Extract the substring enclosed in braces
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
            file_name (str): Path to the JSON template file.
            inputs (dict): Input values for template parameters.

        Returns:
            ChatPromptTemplate: Constructed prompt template.
        """
        template = FileHandler().read_file(file_name)

        # Normalize structure
        system_msg = "\n".join(template.get("system", []))
        human_msg = "\n".join(template.get("human", []))
        params = template.get("params", [])
        examples = template.get("examples", [])

        # Resolve parameter placeholders
        input_template = self._resolve_template_params(params, inputs)

        # Build few-shot prompt if examples exist
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
        Resolve template parameters using provided input data.

        Args:
            params (list): Parameter structure from template.
            inputs (dict): Input data to map to parameters.

        Returns:
            dict: Resolved key-value pairs for prompt filling.
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
        Build a few-shot message prompt from examples.

        Args:
            examples (list): List of example dictionaries containing
                'input', 'reasoning', and 'output' fields.

        Returns:
            FewShotChatMessagePromptTemplate: The constructed few-shot prompt.
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
        Invoke the LLM with a built prompt and retrieve its output.

        Args:
            file_name (str): Path to the prompt template file.
            input_state (dict): Execution state from which to
                        extract parameters for prompt filling.
            lower (bool): Whether to convert the response to lowercase.

        Returns:
            str: Cleaned and formatted LLM response.
        """
        prompt, input_prompt = self.build_from_file(file_name, input_state)
        chain = prompt | self.llm | self.parser
        result = chain.invoke(input_prompt)
        time.sleep(self.seconds)

        # Post-processing of model response
        result = self._clean_response(result, lower)
        return result

    def _clean_response(self, result: str, lower: bool) -> str:
        """
        Clean and normalize the raw LLM output.

        Args:
            result (str): Raw model response.
            lower (bool): Whether to convert to lowercase.

        Returns:
            str: Cleaned text output.
        """
        if lower:
            result = result.lower()

        for marker in ["risultato:", "risposta:", "result:", "response:"]:
            if marker in result.lower():
                idx = result.lower().index(marker) + len(marker)
                result = result[idx:]

        result = result.strip()
        return "" if result == "''" else result
