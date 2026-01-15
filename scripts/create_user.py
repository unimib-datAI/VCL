import argparse
import sys

from pathlib import Path

# Root path of the project (two levels up from this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.storage import Storage

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the DQL application.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="DQL - Registry User Creation",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-username",
        action="store",
        dest="username",
        required=True,
        help="Username for the new user.",
    )
    
    parser.add_argument(
        "-email",
        action="store",
        dest="email",
        required=False,
        help="Email for the new user.",
    )

    parser.add_argument(
        "-password",
        action="store",
        dest="password",
        required=False,
        help="Password for the new user.",
    )

    parser.add_argument(
        "-role",
        action="store",
        dest="role",
        required=False,
        default="Altro",
        help="Role for the new user (default: Altro).",
    )

    return parser.parse_args()


def main() -> None:
    """
    Entry point for the DQL CLI application.

    Parses command-line options, initializes configuration,
    and launches the Streamlit interface.
    """
    opts = parse_args()
    
    storage = Storage.get_instance()
    
    result, user = storage.register_user(opts.username, opts.email, opts.password, opts.role)
    if result and user:
        print(f"User '{opts.username}' created successfully with role '{opts.role}'.")
    else:
        print(f"Error: Could not create user '{opts.username}'.")
        if isinstance(user, str) and user:
            print(f"Reason: {user}")


if __name__ == "__main__":
    main()
