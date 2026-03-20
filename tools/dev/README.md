# 🛠 Development & Validation Tools

This directory contains scripts to ensure code quality and environment consistency.

## 🚀 `check.py`
The primary quality gate for the project. It automates linting, type checking, unit testing, and Docker integration testing.

### Usage
- **Full Check**: `python tools/dev/check.py`
- **Interactive Menu**: `python tools/dev/check.py --settings`

### Features
1. **Linters**: Runs `pre-commit` hooks (trailing whitespace, ruff, etc.).
2. **Type Checking**: Full `mypy` validation with cache clearing.
3. **Unit Tests**: Executes `pytest` with local environment settings.
4. **Docker Validation**:
   - Builds images from scratch.
   - Starts the full stack.
   - Runs Django internal checks and migration validation inside the container.
   - Automatically cleans up resources.

## 🌳 `generate_project_tree.py`
Generates a visual representation of the project structure for documentation purposes.
