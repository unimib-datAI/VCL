"""
Utility functions for reading and writing text and JSON files.

Responsibilities:
- Provide a consistent interface for handling `.txt` and `.json` files.
- Auto-detect file type based on extension.
- Ensure directories exist before writing.

Functions:
- read_file(path): Reads `.txt` files as strings or `.json` files as dict/list.
- write_file(path, data): Writes strings to `.txt` files or structured data to `.json`.
"""

import os
import json
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
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        if str(path).endswith(".json"):
            json.dump(data, f, indent=4, ensure_ascii=False)  # Pretty-print JSON
        else:
            f.write(str(data))  # Write raw text
