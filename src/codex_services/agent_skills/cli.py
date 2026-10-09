import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from codex_services.agent_skills.fs_transaction import FSError
from codex_services.agent_skills.orchestrator import OrchestratorError, check_status, perform_delete, perform_install


def main(args: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m codex_services.agent_skills")
    parser.add_argument("action", choices=["install", "update", "delete", "status"])
    parser.add_argument("--project", required=True, help="Path to project root")

    parsed = parser.parse_args(args)

    project_dir = Path(parsed.project).absolute()
    if not project_dir.is_dir():
        print(f"Error: Project directory does not exist or is not a directory: {project_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        if parsed.action == "install":
            perform_install(project_dir, update=False)
            print("Installed successfully.")
        elif parsed.action == "update":
            perform_install(project_dir, update=True)
            print("Updated successfully.")
        elif parsed.action == "delete":
            perform_delete(project_dir)
            print("Deleted successfully.")
        elif parsed.action == "status":
            is_valid, msg = check_status(project_dir)
            print(msg)
            if not is_valid:
                sys.exit(1)
    except (OrchestratorError, FSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
