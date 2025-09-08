from graph import Graph

from utils.config import Config

import argparse
import uvicorn

def parse_args():
    """ parse command line input """
    
    parser = argparse.ArgumentParser(description="DQL",
                                     formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument("-api", action="store", dest="api_key", required=False,
                        help="API Key for Gemini. If not specified, the settings/api_key.txt file is read.")
    parser.add_argument("-wait", action="store", dest="seconds", required=False,
                        help="Number of seconds the system should wait after each call to an LLM (useful if using free plans).")
    parser.add_argument("-rag", action="store_true", dest="rag",
                        help="Indicates whether the entire documents (unspecified parameter) or only the relevant chunks (specified parameter) should be retrieved.")
    parser.add_argument("-max_iterations", action="store", dest="max_iterations", required=False,
                        help="Maximum number of rewrite attempts for a query.")
    parser.add_argument("-save_image", action="store_true", dest="save_image", required=False,
                        help="Saving the rewrite graph image.")

    options = parser.parse_args()

    return options

def main():
    opts = parse_args()
    Config.get_instance(opts)
    
    if opts.save_image:
        getGraphImage()
    
    uvicorn.run("app:app")
    
def getGraphImage():
    graph = Graph(Config.get_instance()).graph
    with open("images/graph.png", "wb") as f:
        f.write(graph.get_graph().draw_mermaid_png())
    
if __name__ == "__main__":
    main()