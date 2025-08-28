import sys

from graph import build_graph

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from utils.config_graph import Config

import subprocess
import argparse

def parse_args():
    """ parse command line input """
    
    parser = argparse.ArgumentParser(description="DQL",
                                     formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument("-api", action="store", dest="api_key", required=False,
                        help="API Key for Gemini. If not specified, the settings/api_key.txt file is read.")
    parser.add_argument("-wait", action="store", dest="seconds", required=False,
                        help="Number of seconds the system should wait after each call to an LLM (useful if using free plans).")
    parser.add_argument("-max_iterations", action="store", dest="max_iterations", required=False,
                        help="Maximum number of rewrites of a query.")
    parser.add_argument("-save_image", action="store_true", dest="save_image", required=False,
                        help="Maximum number of rewrites of a query.")

    options = parser.parse_args()

    return options

def main():
    opts = parse_args()
    cfg = Config.get_instance(opts)
    
    file_directory = Path(__file__).resolve().parent
    
    if opts.save_image:
        getGraphImage()
    
    subprocess.call(
        ["uvicorn", "app:app", "--reload"],
        cwd=file_directory
    )
    
def getGraphImage():
    graph = build_graph()
    with open("images/graph.png", "wb") as f:
        f.write(graph.get_graph().draw_mermaid_png())
    
if __name__ == "__main__":
    main()