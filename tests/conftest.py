"""Shared test fixtures."""

import pytest
from codex_core.core.pii import PIIRegistry


@pytest.fixture(autouse=True)
def reset_pii_registry() -> None:
    PIIRegistry._registered_fields = frozenset()
    yield
    PIIRegistry._registered_fields = frozenset()
