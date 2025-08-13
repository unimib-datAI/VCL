import os

def read_file(path: str) -> str:
    """Read a text file and return its stripped content."""
    with open(path, "r") as f:
        return f.read().strip()

def write_file(path: str, key: str):
    """Write the given string to a file, creating directories if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(key)