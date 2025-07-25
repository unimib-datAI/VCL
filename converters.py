import json

class OutputConverter:
    @staticmethod
    def query_in_dict(output: str) -> dict:
        clean = output.replace("\"\"", "\"Altro\"").replace("json", "").replace("`", "").strip()
        clean = clean[clean.index("{") : clean.index("}") + 1]
        return json.loads(clean)

    @staticmethod
    def query_in_list(output: str) -> list:
        clean = output.replace("\"\"", "\"Altro\"").replace("python", "").replace("`", "").strip()
        clean = clean[clean.index("[") : clean.index("]") + 1]
        return eval(clean)

    @staticmethod
    def convert_key(key: str, mapping: dict) -> str:
        return mapping.get(key, "Altro")