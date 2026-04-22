import argparse
import sys
import subprocess
import time
from pathlib import Path

from scripts.evaluation.main import evaluation

def parse_args() -> argparse.Namespace:
    """
    Parse arguments just enough to know if we are in evaluation mode.
    The rest of the arguments will be forwarded to run_api.py.
    """
    parser = argparse.ArgumentParser(
        description="DQL - Orchestrator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # We only explicitly parse the evaluation flag here
    parser.add_argument(
        "-evaluation_mode",
        action="store_true",
        dest="evaluation_mode",
        help="Run only the evaluation script.",
    )
    
    # parse_known_args allows us to ignore all the other API-specific flags
    opts, _ = parser.parse_known_args()
    return opts

def _launch_api() -> subprocess.Popen:
    print("Starting Uvicorn API...")
    # sys.argv[1:] contains all the raw arguments passed by the user
    # We forward them exactly as they are to the API script
    cmd = [sys.executable, "run_api.py"] + sys.argv[1:]
    return subprocess.Popen(cmd)

def _launch_streamlit() -> subprocess.Popen:
    print("Starting Streamlit UI...")
    cmd = [sys.executable, "run_streamlit.py"]
    return subprocess.Popen(cmd)

def main() -> None:
    opts = parse_args()
    
    print("Starting Docker containers...")
    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    
    api_process = None
    ui_process = None
    
    try:
        if opts.evaluation_mode:
            evaluation()
        else:
            # 1. Start API Subprocess
            api_process = _launch_api()
            
            # Allow the API time to bind to port 8000
            time.sleep(2) 
            
            # 2. Start Streamlit Subprocess
            ui_process = _launch_streamlit()

            # 3. Wait for the UI process to close
            ui_process.wait()

    except KeyboardInterrupt:
        print("\nManual interruption (CTRL+C) detected. Shutting down...")
    
    finally:
        if ui_process is not None:
            print("Stopping Streamlit...")
            ui_process.terminate()
            
        if api_process is not None:
            print("Stopping Uvicorn API...")
            api_process.terminate()

        print("Shutting down Docker containers...")
        subprocess.run(["docker", "compose", "down"])
        print("Shutdown complete.")

if __name__ == "__main__":
    main()