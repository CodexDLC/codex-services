"""Quality gate for codex-services."""

import sys
from pathlib import Path

from codex_core.dev.check_runner import BaseCheckRunner


class CheckRunner(BaseCheckRunner):
    PROJECT_NAME = "codex-services"
    INTEGRATION_REQUIRES = "pure Python, no external deps"

    def run_tests(self, marker: str = "unit") -> bool:
        if marker != "integration":
            return super().run_tests(marker)
        self.print_step("Running Integration Tests")
        success, _ = self.run_command(
            f'"{sys.executable}" -m pytest {self.tests_dir} -m {marker} -v --tb=short --no-cov'
        )
        if success:
            self.print_success("Integration tests passed.")
        else:
            self.print_error("Integration tests failed.")
        return success


if __name__ == "__main__":
    CheckRunner(Path(__file__).parent.parent.parent).main()
