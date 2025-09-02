import os
import json
from typing import Union

def read_file(path: str) -> Union[str, dict, list]:
    """
    Read a text or JSON file.
    - If the file ends with .txt → returns a string (file content, stripped).
    - If the file ends with .json → returns a Python object (dict or list).
    """
    with open(path, "r", encoding="utf-8") as f:
        if str(path).endswith(".json"):
            return json.load(f)
        return f.read().strip()

def write_file(path: str, data: Union[str, dict, list]):
    """
    Write a text or JSON file.
    - If the file ends with .txt → writes the string as-is.
    - If the file ends with .json → writes JSON formatted with indentation.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if str(path).endswith(".json"):
            json.dump(data, f, indent=4, ensure_ascii=False)
        else:
            f.write(str(data))