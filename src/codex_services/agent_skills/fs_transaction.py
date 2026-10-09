"""Same-volume staged writes with best-effort rollback after ordinary I/O errors."""

import errno
import os
import shutil
import stat
import tempfile
from contextlib import suppress
from pathlib import Path


class FSError(Exception):
    pass


def validate_no_symlinks(path: Path) -> Path:
    """Inspect every existing component with lstat, including dangling links."""
    path = path.absolute()
    parts = list(reversed((path, *path.parents)))
    for index, part in enumerate(parts):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise FSError(f"Cannot inspect {part}: {exc}") from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        ):
            raise FSError(f"Symlink or reparse point detected: {part}")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise FSError(f"Non-directory ancestor: {part}")
    return path


def check_regular_file(path: Path) -> None:
    validate_no_symlinks(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise FSError(f"Cannot inspect {path}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise FSError(f"Not a regular file: {path}")


class FSTransaction:
    def __init__(self, project_dir: Path):
        self.project_dir = validate_no_symlinks(project_dir)
        if not self.project_dir.is_dir():
            raise FSError("Project is not a directory")
        self.temp_dir = Path(tempfile.mkdtemp(prefix=".codex-services-tx-", dir=self.project_dir))
        self.backup_dir = self.temp_dir / "backup"
        self.stage_dir = self.temp_dir / "stage"
        self.backup_dir.mkdir()
        self.stage_dir.mkdir()
        self.to_write: list[tuple[Path, bytes]] = []
        self.to_delete: list[Path] = []
        self.to_prune: list[Path] = []
        self._created_dirs: list[Path] = []
        self._removed_dirs: list[Path] = []
        self._snapshots: dict[Path, Path | None] = {}
        self._retain = False

    def _target(self, target: Path) -> Path:
        target = validate_no_symlinks(target)
        if not target.is_relative_to(self.project_dir) or target.is_relative_to(self.temp_dir):
            raise FSError("Target outside project or inside transaction directory")
        check_regular_file(target)
        return target

    def stage_write(self, target: Path, content: bytes) -> None:
        self.to_write.append((self._target(target), content))

    def stage_delete(self, target: Path) -> None:
        target = self._target(target)
        if target.exists():
            self.to_delete.append(target)

    def stage_prune_empty(self, directory: Path) -> None:
        directory = validate_no_symlinks(directory)
        if not directory.is_relative_to(self.project_dir) or directory == self.project_dir:
            raise FSError("Unsafe directory cleanup target")
        self.to_prune.append(directory)

    def _make_parent(self, parent: Path) -> None:
        missing: list[Path] = []
        current = parent
        while not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            directory.mkdir()
            self._created_dirs.append(directory)

    def apply(self) -> None:
        targets = list(dict.fromkeys([*self.to_delete, *(p for p, _ in self.to_write)]))
        if len(targets) != len(self.to_delete) + len(self.to_write):
            raise FSError("A target appears in multiple operations")
        try:
            # Snapshot every existing destination before the first mutation.
            for index, target in enumerate(targets):
                self._target(target)
                backup = None
                if target.exists():
                    backup = self.backup_dir / f"backup_{index}"
                    shutil.copy2(target, backup)
                self._snapshots[target] = backup
            for index, (_, data) in enumerate(self.to_write):
                (self.stage_dir / f"write_stg_{index}").write_bytes(data)
            for target in self.to_delete:
                target.unlink()
            for index, (target, _) in enumerate(self.to_write):
                self._make_parent(target.parent)
                os.replace(self.stage_dir / f"write_stg_{index}", target)
            for directory in sorted(set(self.to_prune), key=lambda p: len(p.parts), reverse=True):
                validate_no_symlinks(directory)
                try:
                    directory.rmdir()
                    self._removed_dirs.append(directory)
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    if exc.errno not in {errno.ENOTEMPTY, errno.EEXIST} and getattr(exc, "winerror", None) != 145:
                        raise
        except Exception as exc:
            try:
                self.rollback()
            except FSError as recovery:
                self._retain = True
                raise FSError(
                    f"Transaction failed: {exc}. Recovery failed: {recovery}. Backups retained at {self.temp_dir}"
                ) from exc
            raise FSError(f"Transaction failed and was rolled back: {exc}") from exc

    def rollback(self) -> None:
        errors: list[str] = []
        for directory in reversed(self._removed_dirs):
            try:
                directory.mkdir(exist_ok=True)
            except Exception as exc:
                errors.append(f"{directory}: {exc}")
        for target, backup in reversed(list(self._snapshots.items())):
            try:
                if backup is None:
                    if target.exists():
                        target.unlink()
                else:
                    self._make_parent(target.parent)
                    # Copy leaves the sole recovery copy intact if restoration fails.
                    shutil.copy2(backup, target)
            except Exception as exc:
                errors.append(f"{target}: {exc}")
        for directory in reversed(self._created_dirs):
            with suppress(OSError):
                directory.rmdir()
        if errors:
            raise FSError("; ".join(errors))

    def cleanup(self) -> None:
        if self._retain:
            return
        root = self.temp_dir.absolute()
        if root.parent != self.project_dir or not root.name.startswith(".codex-services-tx-"):
            raise FSError("Unsafe transaction cleanup path")
        validate_no_symlinks(root)
        shutil.rmtree(root)

    def __enter__(self) -> "FSTransaction":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.cleanup()
