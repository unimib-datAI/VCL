import json
import os

def retrieve_doc_paths(project_root: str, owner: str = "vitali"):
    paths = []
    
    documents_folder = os.path.join(project_root, "documents", "corpus", owner)
    
    for file_name in os.listdir(documents_folder):
        f = os.path.join(documents_folder, file_name)
        
        if os.path.isdir(f):
            continue

        ext = f.split(".")[-1].lower()
        try:
            if ext in ("json"):
                with open(f, encoding="utf-8", errors="ignore") as file:
                    content = json.load(file)
            else:
                continue
        except Exception:
            content = {}
            
        if content.get("owner") != owner:
            continue

        paths.append(f)
    return paths
