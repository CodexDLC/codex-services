import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from codex_services.agent_skills.cli import main
from codex_services.agent_skills.fs_transaction import FSError
from codex_services.agent_skills.manifest_rules import (
    MANIFEST_NAME,
    MARKER_END,
    MARKER_START,
    ManifestError,
    parse_manifest,
    update_agents_md_bytes,
    validate_normalized_posix_path,
)
from codex_services.agent_skills.orchestrator import OrchestratorError, check_status, perform_delete, perform_install

pytestmark = pytest.mark.unit


@pytest.fixture
def project_dir(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_bytes(b"Header\n")
    return tmp_path


@pytest.fixture
def dummy_payload():
    return {"SKILL.md": b"# Skill content", "references/ref.md": b"Ref content"}


# 1. Parameterize malformed paths
@pytest.mark.parametrize(
    "bad_path",
    [
        "C:\\bad\\path",
        "\\bad\\path",
        "C:bad",
        "../escape",
        "/absolute",
        "./current",
        "empty//segment",
        "trailing ",
        "trailing.",
        "CON",
        "prn.txt",
        "COM1",
    ],
)
def test_malformed_paths(bad_path):
    with pytest.raises(ManifestError):
        validate_normalized_posix_path(bad_path)


# 2. Schema/hash corruption
@pytest.mark.parametrize(
    "corrupt_manifest",
    [
        b"",
        b"{bad json",
        b"[]",
        b'{"version": "2.0"}',
        b'{"version": "1.0"}',  # missing package_version
        b'{"version": "1.0", "package_version": "1", "files": {"SKILL.md": "short"}}',  # invalid hash
        b'{"version": "1.0", "package_version": "1", "files": {"other.md": "a"*64}}',  # missing SKILL.md
    ],
)
def test_schema_hash_corruption(corrupt_manifest):
    with pytest.raises(ManifestError):
        parse_manifest(corrupt_manifest)


# 3. Missing files / status
def test_missing_files_status(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)

    skill_dir = project_dir / ".agents/skills/codex-services"
    (skill_dir / "SKILL.md").unlink()

    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        is_valid, msg = check_status(project_dir)
        assert not is_valid
        assert "Missing file" in msg


# 4. New unowned collision
def test_new_unowned_collision(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)

    skill_dir = project_dir / ".agents/skills/codex-services"
    (skill_dir / "unowned.md").write_text("unowned")

    new_payload = dummy_payload.copy()
    new_payload["unowned.md"] = b"colliding"

    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=new_payload),
        pytest.raises(OrchestratorError, match="colliding with existing unowned file"),
    ):
        perform_install(project_dir, update=True)


# 5. AGENTS symlink and parent symlink/junction
@pytest.mark.skipif(os.name != "nt", reason="Windows specific symlink/junction check")
def test_agents_symlink_fails(project_dir, dummy_payload):
    agents_md = project_dir / "AGENTS.md"
    agents_md.unlink()

    target = project_dir / "real.md"
    target.write_text("real")
    try:
        os.symlink(target, agents_md)
    except OSError:
        pytest.skip("OS cannot create symlink")

    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(FSError, match="Symlink detected"),
    ):
        perform_install(project_dir)


# 6. Ordinary failure restoring exact before snapshot
def test_rollback_on_failure(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)

    skill_dir = project_dir / ".agents/skills/codex-services"
    orig_skill = (skill_dir / "SKILL.md").read_bytes()
    orig_manifest = (skill_dir / MANIFEST_NAME).read_bytes()
    orig_agents = (project_dir / "AGENTS.md").read_bytes()

    new_payload = {"SKILL.md": b"# New", "references/ref.md": b"New Ref"}

    original_replace = os.replace
    raised = [False]

    def fake_replace(src, dst):
        if dst.name == "AGENTS.md" and "write_stg" in str(src) and not raised[0]:
            raised[0] = True
            raise OSError("Injected disk error")
        original_replace(src, dst)

    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=new_payload),
        patch("os.replace", side_effect=fake_replace),
        pytest.raises(FSError, match="Transaction failed"),
    ):
        perform_install(project_dir, update=True)

    assert (skill_dir / "SKILL.md").read_bytes() == orig_skill
    assert (skill_dir / MANIFEST_NAME).read_bytes() == orig_manifest
    assert (project_dir / "AGENTS.md").read_bytes() == orig_agents


# 7. No Django imports CLI, CLI required existing project
def test_cli_requires_project(capsys):
    with pytest.raises(SystemExit) as e:
        main(["install", "--project", "/does/not/exist/ever"])
    assert e.value.code == 1

    # Check no django imported
    import subprocess
    import sys

    cmd_script = "import sys; import codex_services.agent_skills.cli; sys.exit(1 if 'django' in sys.modules else 0)"
    cmd = [sys.executable, "-c", cmd_script]
    result = subprocess.run(cmd)
    assert result.returncode == 0


# 8. AGENTS pure byte edit markers
def test_agents_byte_preservation():
    orig = b"\xef\xbb\xbfUser Text\r\n"
    new_content = update_agents_md_bytes(orig)
    assert new_content.startswith(b"\xef\xbb\xbfUser Text\r\n")
    assert MARKER_START in new_content

    # Missing/duplicate
    with pytest.raises(ManifestError):
        update_agents_md_bytes(orig + MARKER_START)

    with pytest.raises(ManifestError):
        update_agents_md_bytes(orig + MARKER_START + MARKER_START + MARKER_END)


# 9. No recursive deletion
def test_no_recursive_deletion(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)

    skill_dir = project_dir / ".agents/skills/codex-services"
    (skill_dir / "references/unowned.txt").write_text("keep me")

    perform_delete(project_dir)

    assert not (skill_dir / "SKILL.md").exists()
    assert not (skill_dir / MANIFEST_NAME).exists()
    assert (skill_dir / "references/unowned.txt").exists()
    assert (project_dir / "AGENTS.md").exists()
    assert MARKER_START not in (project_dir / "AGENTS.md").read_bytes()


@pytest.mark.parametrize("original", [b"plain", b"\xef\xbb\xbfplain", b"plain\r\n", b"plain\n"])
def test_agents_roundtrip_preserves_original_bytes(original):
    installed = update_agents_md_bytes(original)
    assert update_agents_md_bytes(installed, remove=True) == original


def test_agents_roundtrip_preserves_later_user_addition():
    installed = update_agents_md_bytes(b"plain")
    assert update_agents_md_bytes(installed + b"\nUser addition", remove=True) == b"plain\nUser addition"


@pytest.mark.parametrize(
    "name", [".manifest.json", "AGENTS.md", "foo/../bar", "COM9.md", "foo/aux.txt", "a/<b>", "a/?b", "a/b|c"]
)
def test_manifest_rejects_forbidden_owned_paths(name):
    content = json.dumps(
        {
            "version": "1.0",
            "skill": "codex-services",
            "package_version": "1",
            "agents_created": False,
            "files": {"SKILL.md": "a" * 64, name: "b" * 64},
        }
    ).encode()
    with pytest.raises(ManifestError):
        parse_manifest(content)


def test_manifest_rejects_case_alias_and_parent_conflict():
    for extra in ({"skill.MD": "b" * 64}, {"SKILL.md/child": "b" * 64}):
        content = json.dumps(
            {
                "version": "1.0",
                "skill": "codex-services",
                "package_version": "1",
                "agents_created": False,
                "files": {"SKILL.md": "a" * 64, **extra},
            }
        ).encode()
        with pytest.raises(ManifestError):
            parse_manifest(content)


def test_status_detects_corrupt_instruction(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
        agents = project_dir / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"codex-services](", b"other-skill]("))
        assert check_status(project_dir)[0] is False


def test_update_absent_does_not_adopt(project_dir, dummy_payload):
    before = (project_dir / "AGENTS.md").read_bytes()
    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(OrchestratorError),
    ):
        perform_install(project_dir, update=True)
    assert (project_dir / "AGENTS.md").read_bytes() == before


def test_delete_refuses_modified_owned_file(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    target = project_dir / ".agents/skills/codex-services/SKILL.md"
    target.write_bytes(b"user customization")
    with pytest.raises(OrchestratorError, match="locally edited"):
        perform_delete(project_dir)
    assert target.read_bytes() == b"user customization"


def test_delete_then_install(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
        perform_delete(project_dir)
        assert not (project_dir / ".agents/skills/codex-services").exists()
        perform_install(project_dir)
        assert check_status(project_dir)[0] is True


def test_status_refuses_dangling_symlink(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    target = project_dir / ".agents/skills/codex-services/SKILL.md"
    target.unlink()
    try:
        target.symlink_to(project_dir / "missing")
    except OSError:
        pytest.skip("OS cannot create symlink")
    with pytest.raises(FSError):
        check_status(project_dir)


def test_update_rejects_unowned_parent_directory(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    skill_dir = project_dir / ".agents/skills/codex-services"
    (skill_dir / "unowned").write_bytes(b"user")
    expanded = {**dummy_payload, "unowned/child.md": b"new"}
    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=expanded),
        pytest.raises((OrchestratorError, FSError)),
    ):
        perform_install(project_dir, update=True)
    assert (skill_dir / "unowned").read_bytes() == b"user"


def test_transaction_stage_is_inside_project(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    from codex_services.agent_skills.fs_transaction import FSTransaction

    with FSTransaction(project_dir) as tx:
        assert tx.temp_dir.parent == project_dir


def test_manifest_rejects_wrong_identity_and_duplicate_json_key():
    valid = json.dumps(
        {
            "version": "1.0",
            "skill": "another-skill",
            "package_version": "1",
            "agents_created": False,
            "files": {"SKILL.md": "a" * 64},
        }
    ).encode()
    with pytest.raises(ManifestError):
        parse_manifest(valid)
    duplicated = valid.replace(b'"skill": "another-skill"', b'"skill": "codex-services", "skill": "codex-services"')
    with pytest.raises(ManifestError):
        parse_manifest(duplicated)


def test_update_refuses_owned_edit(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    target = project_dir / ".agents/skills/codex-services/SKILL.md"
    target.write_bytes(b"user edit")
    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(OrchestratorError, match="locally edited"),
    ):
        perform_install(project_dir, update=True)
    assert target.read_bytes() == b"user edit"


def test_orphan_block_refused_without_manifest(project_dir, dummy_payload):
    agents = project_dir / "AGENTS.md"
    agents.write_bytes(update_agents_md_bytes(agents.read_bytes()))
    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(OrchestratorError, match="Orphan"),
    ):
        perform_install(project_dir)
    with pytest.raises(OrchestratorError):
        perform_delete(project_dir)


def test_mid_delete_failure_restores_every_owned_file(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    skill_dir = project_dir / ".agents/skills/codex-services"
    original = {
        path: path.read_bytes()
        for path in [
            skill_dir / "SKILL.md",
            skill_dir / "references/ref.md",
            skill_dir / MANIFEST_NAME,
            project_dir / "AGENTS.md",
        ]
    }
    original_unlink = os.unlink
    failed = [False]

    def fail_once(path, *args, **kwargs):
        if Path(path).name == MANIFEST_NAME and not failed[0]:
            failed[0] = True
            raise OSError("injected deletion error")
        return original_unlink(path, *args, **kwargs)

    with patch("pathlib.Path.unlink", side_effect=fail_once), pytest.raises(FSError, match="rolled back"):
        perform_delete(project_dir)
    assert all(path.read_bytes() == content for path, content in original.items())


@pytest.mark.skipif(os.name != "nt", reason="Windows junction")
def test_junction_ancestor_rejected(project_dir, dummy_payload):
    import subprocess

    real = project_dir / "real"
    real.mkdir()
    junction = project_dir / ".agents"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(real)], capture_output=True, text=True)
    if result.returncode:
        pytest.skip("Cannot create junction")
    with (
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(FSError, match="reparse"),
    ):
        perform_install(project_dir)
    assert list(real.iterdir()) == []


def test_mocked_reparse_ancestor_rejected(project_dir, dummy_payload):
    import stat

    suspect = project_dir / ".agents"
    suspect.mkdir()
    original_lstat = Path.lstat

    def reparse_lstat(path):
        info = original_lstat(path)
        if path == suspect:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return info

    with (
        patch("pathlib.Path.lstat", autospec=True, side_effect=reparse_lstat),
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(FSError, match="reparse"),
    ):
        perform_install(project_dir)


def test_created_agents_file_removed_on_delete(tmp_path, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(tmp_path)
    assert (tmp_path / "AGENTS.md").exists()
    perform_delete(tmp_path)
    assert not (tmp_path / "AGENTS.md").exists()


def test_realistic_agents_roundtrip_and_adjacent_file(project_dir, dummy_payload):
    original = b"\xef\xbb\xbf# Project rules\r\nPreserve this without terminal newline"
    agents = project_dir / "AGENTS.md"
    agents.write_bytes(original)
    adjacent = project_dir / "AGENTS.tmp"
    adjacent.write_bytes(b"unrelated")
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    perform_delete(project_dir)
    assert agents.read_bytes() == original
    assert adjacent.read_bytes() == b"unrelated"


def test_rollback_failure_retains_backup_files(project_dir, dummy_payload):
    with patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload):
        perform_install(project_dir)
    old_copy = __import__("shutil").copy2
    old_replace = os.replace

    def fail_replace(src, dst):
        if Path(dst).name == "AGENTS.md":
            raise OSError("injected write failure")
        return old_replace(src, dst)

    def fail_restore(src, dst, *args, **kwargs):
        if "backup_" in Path(src).name:
            raise OSError("injected restore failure")
        return old_copy(src, dst, *args, **kwargs)

    with (
        patch("os.replace", side_effect=fail_replace),
        patch("shutil.copy2", side_effect=fail_restore),
        patch("codex_services.agent_skills.orchestrator.get_payload_files", return_value=dummy_payload),
        pytest.raises(FSError, match="Backups retained at") as error,
    ):
        perform_install(project_dir, update=True)
    backup_root = Path(str(error.value).split("Backups retained at ", 1)[1])
    assert backup_root.is_dir()
    assert list((backup_root / "backup").iterdir())
