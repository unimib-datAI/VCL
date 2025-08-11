# app.py
from config import Config
from rewriting import Rewriting
from datetime import datetime

import os
import argparse

def parse_args():
    """ parse command line input """
    
    parser = argparse.ArgumentParser(description="DQL",
                                     formatter_class=argparse.RawTextHelpFormatter)
    
    #parser.add_argument("-q", action="store", dest="query", required=True,
    #                    help="The query to execute")
    
    parser.add_argument("-api", action="store", dest="api_key", required=False,
                        help="API Key for Gemini. If not specified, the settings/api_key.txt file is read.")
    parser.add_argument("-rag", action="store_true", dest="rag",
                        help="Indicates whether the entire documents (unspecified parameter) or only the relevant chunks (specified parameter) should be retrieved.")

    options = parser.parse_args()

    return options


def main():
    opts = parse_args()
    cfg = Config(opts)

    while True:
        query = input("Input (empty to end): ").strip()
        if not query:
            break

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = os.path.join("outputs", f"{timestamp}.txt")
        os.makedirs("outputs", exist_ok=True)

        with open(out_path, "w") as f:
            f.write(f"Input: {query}\n\n")
            dql = Rewriting(query, cfg)
            print(dql.command)
            

if __name__ == "__main__":
    main()
