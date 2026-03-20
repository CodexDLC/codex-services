"""Auto-marker for unit tests."""

import pytest


def pytest_collection_modifyitems(items: list) -> None:
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
