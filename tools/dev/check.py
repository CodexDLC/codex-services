"""Quality gate for codex-services."""

from pathlib import Path

from codex_core.dev.check_runner import BaseCheckRunner


class CheckRunner(BaseCheckRunner):
    PROJECT_NAME = "codex-services"
    INTEGRATION_REQUIRES = "pure Python, no external deps"
    # CVE-2026-4539: pygments — no fix available yet (latest version)
    AUDIT_FLAGS = "--skip-editable --ignore-vuln CVE-2026-4539"
    RUN_LINT = True
    RUN_TYPES = True
    RUN_SECURITY = True
    RUN_EXTRA_CHECKS = True
    RUN_UNIT_TESTS = True
    RUN_INTEGRATION_TESTS = True


if __name__ == "__main__":
    CheckRunner(Path(__file__).parent.parent.parent).main()
