"""
This module defines the LLM class, a thread-safe singleton that initializes and manages
a Large Language Model (LLM) using LangChain.

Responsibilities:
- Load an API key from either an argument or a local file (`settings/api_key.txt`).
- Set the API key as an environment variable for Google GenAI.
- Initialize and expose the LLM model via LangChain's `init_chat_model`.
- Ensure only one instance of the LLM exists across threads (Singleton pattern).

Dependencies:
- utils.file_manager.read_file, write_file: For reading/writing the API key.
- langchain.chat_models.init_chat_model: For initializing the LLM.
"""

# pylint: disable=invalid-name
import ast
import json
import os
import threading
import time

from pathlib import Path
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate

from bot.utils.file_manager import read_file, write_file


class LLM:
    """
    Singleton class for initializing and managing a Large Language Model (LLM).

    Attributes:
        model_name (str): The default LLM model name.
        provider (str): The provider for the LLM (e.g., Google GenAI).
        llm: The initialized LangChain chat model instance.
    """

    # Singleton instance
    _instance = None
    # Lock to ensure thread-safety when creating the instance
    _lock = threading.Lock()

    # Default LLM model and provider
    model_name: str = "gemini-2.0-flash"
    provider: str = "google_genai"
    
    # Default output parser
    parser = StrOutputParser()

    def __init__(self, api_key: str = None, seconds: int = 5, project_root = None):
        """
        Initialize the LLM class.

        Args:
            api_key (str, optional): API key for the LLM provider.
                If not provided, it is read from `settings/api_key.txt`.
            seconds (int): Delay between LLM calls.

        Raises:
            ValueError: If no API key is provided or found in the settings file.
        """
        # Path where the API key is stored
        api_path = project_root / "settings" / "api_key.txt"

        # If no API key was provided, try reading it from the file
        if not api_key and os.path.exists(api_path) and os.path.isfile(api_path):
            api_key = read_file(api_path)

        # Set the environment variable for the Google GenAI API
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

            # Save the key again (could normalize or update formatting)
            write_file(api_path, api_key)
        else:
            raise ValueError("No API key could be found.")

        # Initialize the LLM model from LangChain
        self.llm = init_chat_model(self.model_name, model_provider=self.provider)
        self.seconds = seconds
        
        # Mark as initialized
        self._initialized = True

    @classmethod
    def get_instance(cls, api_key: str = None, seconds: int = 5, project_root = None):
        """
        Retrieve the singleton instance of the LLM.

        If the instance does not exist, it will be created in a thread-safe manner.

        Args:
            api_key (str, optional): API key to initialize the model.
                If not provided, will attempt to load from file.
            seconds (int): Delay between LLM calls.

        Returns:
            LLM: The singleton instance of the LLM class.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking to prevent race conditions
                if cls._instance is None:
                    cls._instance = cls(api_key, seconds, project_root)
        return cls._instance
    
    @staticmethod
    def str_in_dict(output: str) -> dict:
        """
        Safely extract and parse a JSON object from a string.

        Args:
            output (str): A string containing a JSON object.

        Returns:
            dict: The parsed dictionary, or an empty dict if parsing fails.
        """
        try:
            output = output[output.index("{") : output.rfind("}") + 1]
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return {}

    @staticmethod
    def str_in_list(output: str) -> list:
        """
        Safely extract and parse a Python list from a string.

        Args:
            output (str): A string containing a Python list.

        Returns:
            list: The parsed list, or an empty list if parsing fails.
        """
        try:
            # Find the first and last square brackets and extract substring
            output = output[output.index("[") : output.rfind("]") + 1]
            return ast.literal_eval(output)
        except (ValueError, SyntaxError):
            return []
        
    def invoke_from_file(self, file_name, inputs, lower: bool = False) -> str:
        template = read_file(file_name)
        
        if "system" in template.keys():
            template["system"] = "\n".join(template["system"])
        
        if "human" in template.keys():
            template["human"] = "\n".join(template["human"])
            
        if "params" in template.keys():
            # Fill input template from state
            input_template = {}
            for p in template["params"]:
                if type(p) == list:
                    input_template.update({str("_".join(p)): str(inputs[p[0]][p[1]])})
                else:
                    input_template.update({str(p): str(inputs[p])})

        # Add few-shot examples if available
        if "examples" in template.keys() and not template["examples"] == []:
            template["examples"] = [
                {
                    "input": "\n".join(example["input"]).strip(),
                    "reasoning": example["reasoning"],
                    "output": str(example["output"]),
                }
                for example in template["examples"]
            ]
            
            example_prompt = ChatPromptTemplate.from_messages(
                [
                    HumanMessagePromptTemplate.from_template("{input}"),
                    AIMessagePromptTemplate.from_template(
                        "Ragionamento: {reasoning}\nRisultato: {output}"
                    ),
                ]
            )
            
            few_shot_prompt = FewShotChatMessagePromptTemplate(
                example_prompt=example_prompt, examples=template["examples"]
            )
            
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", template["system"]),
                    few_shot_prompt,
                    ("human", template["human"]),
                ]
            )
        else:
            prompt = ChatPromptTemplate.from_messages(
                [("system", template["system"]), ("human", template["human"])]
            )

        # Invoke LLM and return result
        return self.invoke(prompt, input_template, lower)
        
    def invoke(self, prompt: ChatPromptTemplate, input_template, lower: bool = False) -> str:
        """
        Invoke the LLM with a given prompt and return the response.

        Args:
            prompt (str): The input prompt to send to the LLM.
            input_template: The input template to format the prompt.
            lower (bool): Whether to convert the response to lowercase.

        Returns:
            str: The response from the LLM.
        """
        chain = prompt | self.llm | self.parser
        result = chain.invoke(input_template)
        time.sleep(self.seconds)

        # Post-process: lower-case, strip unwanted tokens
        if lower:
            result = result.lower()
            
        if "risultato:" in result.lower():
            result = result[result.lower().index("risultato:") + 11 :]
            
        if "risposta:" in result.lower():
            result = result[result.lower().index("risposta:") + 10 :]
            
        result = result.strip()
        
        if result == "''":
            result = ""
        
        return result
