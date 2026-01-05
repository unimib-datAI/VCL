import json
import os
import spacy
import subprocess
import sys


from typing import Union

class FileHandler:
    """
    Utility class for reading and writing files in common formats (.txt, .css, .json).

    This class provides static methods to simplify file I/O operations,
    ensuring safe handling of text and JSON content, with automatic
    directory creation when writing files.
    """
    def __init__(self):
        self.nlp = None

    @staticmethod
    def read_file(path: str) -> Union[str, dict, list]:
        """
        Read the contents of a text, CSS, or JSON file.

        Args:
            path (str): The full path to the file.

        Returns:
            Union[str, dict, list]:
                - If the file ends with `.txt` or `.css`, returns the stripped string.
                - If the file ends with `.json`, returns a Python object (dict or list).

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the JSON file cannot be parsed.
            ValueError: If the file extension is not supported.
        """
        # Ensure the file exists before attempting to read
        if not os.path.isfile(path):
            raise FileNotFoundError(f"The specified file does not exist: {path}")

        # Open and process the file according to its extension
        with open(path, "r", encoding="utf-8") as f:
            if str(path).endswith(".json"):
                # Parse JSON content into a Python structure (dict or list)
                return json.load(f)
            elif str(path).endswith((".txt", ".css")):
                # Return plain text or CSS as a trimmed string
                return f.read().strip()
            else:
                # Unsupported file type
                raise ValueError(
                    "Unsupported file type. Supported extensions are: .txt, .css, .json"
                )

    @staticmethod
    def write_file(path: str, data: Union[str, dict, list]) -> None:
        """
        Write data to a file (text or JSON).

        Args:
            path (str): The target file path.
            data (Union[str, dict, list]): Content to be written.
                - Strings are written directly to `.txt` or `.css` files.
                - Dicts and lists are serialized as JSON for `.json` files.

        Notes:
            - Automatically creates parent directories if they do not exist.
            - JSON files are written with UTF-8 encoding and human-readable indentation.

        Raises:
            ValueError: If the file extension is not supported.
        """
        # Ensure that the target directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Open and write the file according to its extension
        with open(path, "w", encoding="utf-8") as f:
            if str(path).endswith(".json"):
                # Serialize Python data as pretty-printed JSON
                json.dump(data, f, indent=4, ensure_ascii=False)
            elif str(path).endswith((".txt", ".css")):
                # Write plain text or CSS content
                f.write(str(data))
            else:
                # Unsupported file type
                raise ValueError(
                    "Unsupported file type. Supported extensions are: .txt, .css, .json"
                )
                
    def _load_spacy(self):
        # Load the Italian spaCy model
        if not self.nlp:
            try:
                self.nlp = spacy.load("it_core_news_sm")
            except OSError:
                subprocess.check_call([sys.executable, "-m", "spacy", "download", "it_core_news_sm"])
                self.nlp = spacy.load("it_core_news_sm")

    def text_analysis(self, text: str, key: str = "parole") -> int:
        """
        Perform a simple text analysis using spaCy (Italian model).

        Args:
            text (str): The input text to analyze.
            key (str): The type of analysis to perform. One of:
                - "parole": Count of words (excluding punctuation and spaces).
                - "caratteri": Count of characters (excluding leading/trailing spaces).
                - "frasi": Count of sentences detected by spaCy.

        Returns:
            int: The computed count (words, characters, or sentences).

        Notes:
            - Requires the `it_core_news_sm` spaCy model to be installed.
            - Returns 0 if the key is invalid.
        """
        # Validate key
        if key not in ["parole", "caratteri", "frasi"]:
            return 0

        # Character count (simple case)
        if key == "caratteri":
            return len(text.strip())

        # Process text with spaCy
        # self._load_spacy()
        # doc = self.nlp(text)

        if key == "parole":
            # Count tokens that are not punctuation or spaces
            return len(text.split())
            # return sum(1 for token in doc if not token.is_punct and not token.is_space)

        # Process text with spaCy
        self._load_spacy()
        doc = self.nlp(text)
        
        if key == "frasi":
            # Count sentences detected by spaCy
            return len(list(doc.sents))
