import json
import runpy
import sys
from pathlib import Path

import pytest

from codex_services.agent_skills.cli import main
from codex_services.agent_skills.manifest_rules import MANIFEST_NAME, MARKER_START, ManifestError, parse_manifest
from codex_services.agent_skills.orchestrator import (
    OrchestratorError,
    check_status,
    get_payload_files,
    perform_delete,
    perform_install,
)

pytestmark = pytest.mark.unit


def test_packaged_payload_has_entrypoint_and_references():
    payload = get_payload_files()
    assert b"name: codex-services" in payload["SKILL.md"]
    for name in ("booking.md", "slot-windows.md", "calendar.md"):
        assert f"references/{name}" in payload
        assert f"references/{name}".encode() in payload["SKILL.md"]


def test_install_update_delete_preserves_unrelated_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    agents = tmp_path / "AGENTS.md"
    original_agents = b"\xef\xbb\xbf# My project\r\nKeep this exact.\r\n"
    agents.write_bytes(original_agents)
    payload = {"SKILL.md": b"first", "references/guide.md": b"reference"}
    monkeypatch.setattr("codex_services.agent_skills.orchestrator.get_payload_files", lambda: payload)
    perform_install(tmp_path)
    skill_dir = tmp_path / ".agents/skills/codex-services"
    assert check_status(tmp_path)[0]
    assert agents.read_bytes().startswith(original_agents)
    assert MARKER_START in agents.read_bytes()
    manifest = parse_manifest((skill_dir / MANIFEST_NAME).read_bytes())
    assert set(manifest["files"]) == set(payload)
    assert manifest["package_version"]

    extra = skill_dir / "references/local.md"
    extra.write_bytes(b"local")
    payload = {"SKILL.md": b"second", "references/new.md": b"new"}
    perform_install(tmp_path, update=True)
    assert check_status(tmp_path)[0]
    assert (skill_dir / "SKILL.md").read_bytes() == b"second"
    assert not (skill_dir / "references/guide.md").exists()
    assert extra.read_bytes() == b"local"

    perform_delete(tmp_path)
    assert not (skill_dir / "SKILL.md").exists()
    assert extra.read_bytes() == b"local"
    assert agents.read_bytes() == original_agents


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_local_edit_blocks_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str):
    payload = {"SKILL.md": b"original"}
    monkeypatch.setattr("codex_services.agent_skills.orchestrator.get_payload_files", lambda: payload)
    perform_install(tmp_path)
    skill = tmp_path / ".agents/skills/codex-services/SKILL.md"
    skill.write_bytes(b"local edit")
    agents_before = (tmp_path / "AGENTS.md").read_bytes()
    manifest_before = (skill.parent / MANIFEST_NAME).read_bytes()
    if operation == "update":
        payload = {"SKILL.md": b"new version"}
    with pytest.raises(OrchestratorError, match="locally edited managed content"):
        if operation == "update":
            perform_install(tmp_path, update=True)
        else:
            perform_delete(tmp_path)
    assert skill.read_bytes() == b"local edit"
    assert (tmp_path / "AGENTS.md").read_bytes() == agents_before
    assert (skill.parent / MANIFEST_NAME).read_bytes() == manifest_before
    assert not check_status(tmp_path)[0]


def test_new_unowned_collision_blocks_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = {"SKILL.md": b"first"}
    monkeypatch.setattr("codex_services.agent_skills.orchestrator.get_payload_files", lambda: payload)
    perform_install(tmp_path)
    skill_dir = tmp_path / ".agents/skills/codex-services"
    unowned = skill_dir / "local.md"
    unowned.write_bytes(b"my file")
    payload = {"SKILL.md": b"second", "local.md": b"collision"}
    with pytest.raises(OrchestratorError, match="colliding"):
        perform_install(tmp_path, update=True)
    assert unowned.read_bytes() == b"my file"
    assert (skill_dir / "SKILL.md").read_bytes() == b"first"


def test_no_adoption_or_manifest_tampering(tmp_path: Path):
    skill_dir = tmp_path / ".agents/skills/codex-services"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"unowned")
    with pytest.raises(OrchestratorError, match="without ownership manifest"):
        perform_install(tmp_path)
    with pytest.raises(OrchestratorError, match="ownership manifest"):
        perform_delete(tmp_path)
    assert (skill_dir / "SKILL.md").read_bytes() == b"unowned"
    manifest = {
        "version": "1.0",
        "skill": "codex-services",
        "package_version": "1",
        "agents_created": False,
        "files": {"SKILL.md": "a" * 64, "../escape": "b" * 64},
    }
    with pytest.raises(ManifestError):
        parse_manifest(json.dumps(manifest).encode())


def test_cli_lifecycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    arguments = ["--project", str(tmp_path)]
    main(["install", *arguments])
    assert "Installed successfully" in capsys.readouterr().out
    main(["status", *arguments])
    assert "up to date" in capsys.readouterr().out
    main(["update", *arguments])
    assert "Updated successfully" in capsys.readouterr().out
    main(["delete", *arguments])
    assert "Deleted successfully" in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        main(["status", *arguments])
    assert error.value.code == 1
    assert "Not installed" in capsys.readouterr().out


def test_module_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "argv", ["python -m codex_services.agent_skills", "install", "--project", str(tmp_path)])
    runpy.run_module("codex_services.agent_skills", run_name="__main__")
    assert (tmp_path / ".agents/skills/codex-services/SKILL.md").exists()


def test_status_detects_new_package_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = {"SKILL.md": b"first"}
    monkeypatch.setattr("codex_services.agent_skills.orchestrator.get_payload_files", lambda: payload)
    perform_install(tmp_path)
    perform_install(tmp_path)  # Idempotent when current.
    payload = {"SKILL.md": b"second"}
    assert "payload differs" in check_status(tmp_path)[1]
    with pytest.raises(OrchestratorError, match="Use update"):
        perform_install(tmp_path)
    payload = {"SKILL.md": b"first", "references/new.md": b"new"}
    assert "file list differs" in check_status(tmp_path)[1]
    monkeypatch.setattr("codex_services.agent_skills.orchestrator.get_package_version", lambda: "future")
    assert "package version differs" in check_status(tmp_path)[1]


def test_corrupt_manifest_and_missing_instruction_are_reported(tmp_path: Path):
    perform_install(tmp_path)
    skill_dir = tmp_path / ".agents/skills/codex-services"
    manifest = skill_dir / MANIFEST_NAME
    saved_manifest = manifest.read_bytes()
    manifest.write_bytes(b"{corrupt")
    assert "Corrupt ownership manifest" in check_status(tmp_path)[1]
    with pytest.raises(OrchestratorError, match="Corrupt ownership manifest"):
        perform_delete(tmp_path)
    manifest.write_bytes(saved_manifest)
    (tmp_path / "AGENTS.md").unlink()
    assert "instruction missing" in check_status(tmp_path)[1]
    with pytest.raises(OrchestratorError, match="instruction missing"):
        perform_install(tmp_path, update=True)
    with pytest.raises(OrchestratorError, match="instruction missing"):
        perform_delete(tmp_path)


def test_cli_reports_managed_content_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    perform_install(tmp_path)
    skill = tmp_path / ".agents/skills/codex-services/SKILL.md"
    skill.write_bytes(b"edited")
    with pytest.raises(SystemExit) as error:
        main(["update", "--project", str(tmp_path)])
    assert error.value.code == 1
    assert "locally edited" in capsys.readouterr().err
