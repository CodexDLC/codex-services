"""Quality gate for codex-services."""

from pathlib import Path

from codex_core.dev.check_runner import BaseCheckRunner


class CheckRunner(BaseCheckRunner):
    """Thin launcher; project policy lives in pyproject.toml."""


if __name__ == "__main__":
    CheckRunner(Path(__file__).parent.parent.parent).main()
