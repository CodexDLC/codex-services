"""Generate project structure tree."""

from pathlib import Path

from codex_core.dev.project_tree import ProjectTreeGenerator

if __name__ == "__main__":
    ProjectTreeGenerator(Path(__file__).parent.parent.parent).interactive()
