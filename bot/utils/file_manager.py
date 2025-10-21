"""
Utility functions for reading and writing text and JSON files, cleaning data structures,
and performing simple text analysis in Italian.

Responsibilities:
- Provide a consistent interface for handling `.txt` and `.json` files.
- Auto-detect file type based on extension.
- Ensure directories exist before writing.
- Offer utilities for recursively cleaning data.
- Perform basic NLP-based text analysis (words, characters, sentences).

Functions:
- read_file(path): Reads `.txt` files as strings or `.json` files as dict/list.
- write_file(path, data): Writes strings to `.txt` files or structured data to `.json`.
- remove_empty_values(data): Recursively remove empty elements from dicts/lists.
- text_analysis(text, key): Compute basic text metrics using spaCy (words, chars, sentences).
"""

import os
import json
import spacy
import subprocess
import sys
from typing import Union


def read_file(path: str) -> Union[str, dict, list]:
    """
    Read a text or JSON file.

    Args:
        path (str): Path to the file.

    Returns:
        Union[str, dict, list]:
            - If the file ends with `.txt`, returns a stripped string.
            - If the file ends with `.json`, returns a Python object (dict or list).

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the JSON file is invalid.
    """
    with open(path, "r", encoding="utf-8") as f:
        if str(path).endswith(".json"):
            return json.load(f)  # Load structured JSON
        return f.read().strip()  # Return plain text


def write_file(path: str, data: Union[str, dict, list]):
    """
    Write a text or JSON file.

    Args:
        path (str): Path to the file.
        data (Union[str, dict, list]): Content to write.
            - Strings are written directly to `.txt` files.
            - Dicts and lists are serialized as JSON for `.json` files.

    Notes:
        - Creates the parent directory if it does not exist.
        - JSON files are written with indentation and UTF-8 encoding.
    """
    # Ensure parent directory exists before writing
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        if str(path).endswith(".json"):
            # Write formatted JSON (human-readable)
            json.dump(data, f, indent=4, ensure_ascii=False)
        else:
            # Write as plain text
            f.write(str(data))


def remove_empty_values(data):
    """
    Recursively remove all elements with empty string values ("")
    or empty containers (dicts/lists) from nested structures.

    Args:
        data (any): The input data (can be dict, list, or other).

    Returns:
        any: The cleaned data with empty elements removed.
    """
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            # Clean nested values recursively
            cleaned_value = remove_empty_values(value)
            # Keep only non-empty items
            if cleaned_value not in ("", {}, []):
                new_dict[key] = cleaned_value
        return new_dict

    elif isinstance(data, list):
        new_list = []
        for item in data:
            cleaned_item = remove_empty_values(item)
            # Append only non-empty elements
            if cleaned_item not in ("", {}, []):
                new_list.append(cleaned_item)
        return new_list

    else:
        # Base case: return the value as is
        return data


def text_analysis(text: str, key: str = "parole") -> int:
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
    # Load the Italian spaCy model
    ensure_spacy_model("it_core_news_sm")
    nlp = spacy.load("it_core_news_sm")

    # Validate key
    if key not in ["parole", "caratteri", "frasi"]:
        return 0

    # Character count (simple case)
    if key == "caratteri":
        return len(text.strip())

    # Process text with spaCy
    doc = nlp(text)

    if key == "parole":
        # Count tokens that are not punctuation or spaces
        return sum(1 for token in doc if not token.is_punct and not token.is_space)

    if key == "frasi":
        # Count sentences detected by spaCy
        return len(list(doc.sents))
    
    
def ensure_spacy_model(model_name: str):
    """
    Checks whether a spaCy template is installed, and installs it if necessary.
    """
    try:
        spacy.load(model_name)
    except OSError:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
