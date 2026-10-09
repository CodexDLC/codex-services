"""Offline orchestration for the optional project agent skill."""

from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path
from typing import Any

from codex_services.agent_skills.fs_transaction import FSError, FSTransaction, check_regular_file, validate_no_symlinks
from codex_services.agent_skills.manifest_rules import (
    MANIFEST_NAME,
    ManifestError,
    build_manifest,
    has_valid_agents_block,
    hash_content,
    parse_manifest,
    update_agents_md_bytes,
)

SKILL_REL_DIR = ".agents/skills/codex-services"


class OrchestratorError(Exception):
    pass


def get_package_version() -> str:
    try:
        return version("codex-services")
    except PackageNotFoundError:
        return "source"


def get_payload_files() -> dict[str, bytes]:
    try:
        root = files("codex_services.agent_skills.resources")
        payload: dict[str, bytes] = {}

        def collect(node: Any, prefix: str = "") -> None:
            for item in node.iterdir():
                if item.name.startswith("__"):
                    continue
                name = f"{prefix}/{item.name}" if prefix else item.name
                if item.is_dir():
                    collect(item, name)
                elif item.is_file():
                    payload[name] = item.read_bytes()

        collect(root)
        # Also validates names, conflicts, and the required SKILL.md.
        build_manifest(get_package_version(), payload)
        return payload
    except (OSError, ManifestError, ModuleNotFoundError) as exc:
        raise OrchestratorError(f"Invalid packaged skill payload: {exc}") from exc


def _paths(project_dir: Path) -> tuple[Path, Path, Path]:
    project = validate_no_symlinks(project_dir)
    if not project.is_dir():
        raise OrchestratorError(f"Project is not a directory: {project}")
    skill_dir = validate_no_symlinks(project / SKILL_REL_DIR)
    if skill_dir.exists() and not skill_dir.is_dir():
        raise FSError(f"Skill destination is not a directory: {skill_dir}")
    manifest_path = validate_no_symlinks(skill_dir / MANIFEST_NAME)
    agents_path = validate_no_symlinks(project / "AGENTS.md")
    check_regular_file(manifest_path)
    check_regular_file(agents_path)
    return skill_dir, manifest_path, agents_path


def _owned(project_dir: Path, manifest_path: Path, skill_dir: Path) -> dict[str, Any] | None:
    if not manifest_path.exists():
        return None
    try:
        data = parse_manifest(manifest_path.read_bytes())
    except (ManifestError, OSError) as exc:
        raise OrchestratorError(f"Corrupt ownership manifest: {exc}") from exc
    # Preflight the entire owned set, including paths that no longer exist.
    for name in data["files"]:
        check_regular_file(validate_no_symlinks(skill_dir.joinpath(*name.split("/"))))
    return data


def _agents_bytes(agents_path: Path) -> bytes:
    try:
        return agents_path.read_bytes() if agents_path.exists() else b""
    except OSError as exc:
        raise OrchestratorError(f"Cannot read AGENTS.md: {exc}") from exc


def _block_state(agents_path: Path) -> bool:
    try:
        return has_valid_agents_block(_agents_bytes(agents_path))
    except ManifestError as exc:
        raise OrchestratorError(f"Corrupt AGENTS.md block: {exc}") from exc


def _disk_matches(skill_dir: Path, owned: dict[str, Any]) -> tuple[bool, str]:
    for name, digest in owned["files"].items():
        target = skill_dir.joinpath(*name.split("/"))
        if not target.exists():
            return False, f"Missing file on disk: {name}"
        try:
            if hash_content(target.read_bytes()) != digest:
                return False, f"File on disk modified or corrupt: {name}"
        except OSError as exc:
            return False, f"Cannot read file on disk: {name}: {exc}"
    return True, ""


def _require_unmodified_owned_files(skill_dir: Path, owned: dict[str, Any]) -> None:
    matches, reason = _disk_matches(skill_dir, owned)
    if not matches:
        raise OrchestratorError(f"Refusing to replace locally edited managed content: {reason}")


def check_status(project_dir: Path) -> tuple[bool, str]:
    skill_dir, manifest_path, agents_path = _paths(project_dir)
    try:
        owned = _owned(project_dir, manifest_path, skill_dir)
        block = _block_state(agents_path)
    except OrchestratorError as exc:
        return False, str(exc)
    if owned is None:
        if block:
            return False, "Orphan AGENTS.md block without ownership manifest."
        if skill_dir.exists():
            return False, "Directory exists but is not managed by this installer."
        return False, "Not installed."
    if not block:
        return False, "AGENTS.md instruction missing."
    matches, reason = _disk_matches(skill_dir, owned)
    if not matches:
        return False, reason
    payload = get_payload_files()
    if owned["package_version"] != get_package_version():
        return False, "Installed package version differs. Needs update."
    if set(owned["files"]) != set(payload):
        return False, "Installed file list differs. Needs update."
    if any(owned["files"][name] != hash_content(content) for name, content in payload.items()):
        return False, "Installed payload differs. Needs update."
    return True, "Installed and up to date."


def perform_install(project_dir: Path, update: bool = False) -> None:
    skill_dir, manifest_path, agents_path = _paths(project_dir)
    owned = _owned(project_dir, manifest_path, skill_dir)
    block = _block_state(agents_path)
    if owned is None:
        if block:
            raise OrchestratorError("Orphan AGENTS.md block without ownership manifest.")
        if update:
            raise OrchestratorError("Not installed; update requires an ownership manifest.")
        if skill_dir.exists():
            raise OrchestratorError("Destination exists without ownership manifest.")
    elif not block:
        raise OrchestratorError("AGENTS.md instruction missing; refusing to modify corrupt installation.")
    elif not update:
        current, message = check_status(project_dir)
        if current:
            return
        raise OrchestratorError(f"Installation exists but is not current: {message}. Use update.")

    if owned is not None:
        _require_unmodified_owned_files(skill_dir, owned)

    payload = get_payload_files()
    new_manifest = build_manifest(
        get_package_version(),
        payload,
        agents_created=owned["agents_created"] if owned else not agents_path.exists(),
    )
    old_files = set(owned["files"]) if owned else set()
    # All possible destinations are inspected before any file is changed.
    for name in set(payload) | old_files:
        target = skill_dir.joinpath(*name.split("/"))
        check_regular_file(validate_no_symlinks(target))
        if target.exists() and name not in old_files:
            raise OrchestratorError(f"New payload file colliding with existing unowned file: {name}")
    try:
        agents_new = update_agents_md_bytes(_agents_bytes(agents_path))
    except ManifestError as exc:
        raise OrchestratorError(f"Invalid AGENTS.md block: {exc}") from exc
    with FSTransaction(project_dir) as tx:
        for name in sorted(old_files - set(payload)):
            target = skill_dir.joinpath(*name.split("/"))
            tx.stage_delete(target)
            _stage_owned_parents(tx, target, skill_dir)
        for name, content in sorted(payload.items()):
            tx.stage_write(skill_dir.joinpath(*name.split("/")), content)
        tx.stage_write(manifest_path, new_manifest)
        tx.stage_write(agents_path, agents_new)
        tx.apply()


def _stage_owned_parents(tx: FSTransaction, target: Path, skill_dir: Path) -> None:
    directory = target.parent
    while directory.is_relative_to(skill_dir):
        tx.stage_prune_empty(directory)
        if directory == skill_dir:
            break
        directory = directory.parent


def perform_delete(project_dir: Path) -> None:
    skill_dir, manifest_path, agents_path = _paths(project_dir)
    owned = _owned(project_dir, manifest_path, skill_dir)
    block = _block_state(agents_path)
    if owned is None:
        if block or skill_dir.exists():
            raise OrchestratorError("No ownership manifest; refusing to delete.")
        return
    if not block:
        raise OrchestratorError("AGENTS.md instruction missing; refusing to delete.")
    _require_unmodified_owned_files(skill_dir, owned)
    try:
        agents_new = update_agents_md_bytes(_agents_bytes(agents_path), remove=True)
    except ManifestError as exc:
        raise OrchestratorError(f"Invalid AGENTS.md block: {exc}") from exc
    with FSTransaction(project_dir) as tx:
        for name in sorted(owned["files"]):
            target = skill_dir.joinpath(*name.split("/"))
            tx.stage_delete(target)
            _stage_owned_parents(tx, target, skill_dir)
        tx.stage_delete(manifest_path)
        tx.stage_prune_empty(skill_dir)
        if owned["agents_created"] and not agents_new:
            tx.stage_delete(agents_path)
        elif agents_new != _agents_bytes(agents_path):
            tx.stage_write(agents_path, agents_new)
        tx.apply()
