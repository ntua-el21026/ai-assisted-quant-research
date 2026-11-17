"""Sequential private acquisition storage with bounded retained file bytes.

The cap covers file contents, including captures, logs, and publication staging.
It does not measure filesystem metadata, memory use, or concurrent writers.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal

from packages.research.artifacts import canonical_json, content_hashes, publish_artifacts

_MAX_BYTES = 1024**3
_BUDGET_LOG = Path("runtime/budget.jsonl")
StorageCode = Literal[
    "private_storage_path",
    "private_storage_exists",
    "private_storage_limit",
    "private_storage_unsafe_path",
    "private_storage_write_failed",
    "private_storage_authority_required",
]


class PrivateStorageError(Exception):
    """Closed failure codes never include private paths, payloads, or subprocess output."""

    def __init__(self, code: StorageCode) -> None:
        super().__init__(code)
        self.code = code


def _check_ancestry(path: Path) -> None:
    if any(entry.is_symlink() for entry in (path, *path.parents)):
        raise PrivateStorageError("private_storage_unsafe_path")
    if any(entry.exists() and not entry.is_dir() for entry in path.parents):
        raise PrivateStorageError("private_storage_unsafe_path")


def _make_directories(path: Path) -> None:
    """Set permissions only on directories created by this call."""
    _check_ancestry(path)
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise PrivateStorageError("private_storage_unsafe_path")
    for entry in reversed(missing):
        entry.mkdir(mode=0o700)
        entry.chmod(0o700)


def _relative_path(relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or "\x00" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or Path(relative).is_absolute()
    ):
        raise PrivateStorageError("private_storage_unsafe_path")
    return Path(relative)


class PrivateStorage:
    """Own one fresh ignored workspace; callers serialize all operations."""

    def __init__(
        self,
        workspace: Path,
        repository: Path,
        max_bytes: int = _MAX_BYTES,
        *,
        storage_guard: Callable[[int], None] | None = None,
    ) -> None:
        if (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or not 0 <= max_bytes <= _MAX_BYTES
        ):
            raise PrivateStorageError("private_storage_limit")
        if ".." in workspace.parts or ".." in repository.parts:
            raise PrivateStorageError("private_storage_path")
        root = workspace.absolute()
        repository = repository.absolute()
        base = repository / "datasets/private/r4b"
        marker = base / ".checkpoint-budget-authority.json"
        if (marker.exists() or marker.is_symlink()) and storage_guard is None:
            raise PrivateStorageError("private_storage_authority_required")
        try:
            relative = root.relative_to(repository)
            if root == base or not root.is_relative_to(base) or not repository.is_dir():
                raise PrivateStorageError("private_storage_path")
            _check_ancestry(root)
            if root.exists():
                raise PrivateStorageError("private_storage_exists")
            ignored = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "check-ignore",
                    "--quiet",
                    "--no-index",
                    "--",
                    relative.as_posix() + "/",
                ],
                capture_output=True,
                check=False,
                timeout=10,
            )
            if ignored.returncode != 0:
                raise PrivateStorageError("private_storage_path")
            _make_directories(root.parent)
            root.mkdir(mode=0o700)
            root.chmod(0o700)
        except PrivateStorageError:
            raise
        except (OSError, ValueError, subprocess.SubprocessError):
            raise PrivateStorageError("private_storage_path") from None
        self._root = root
        self._max_bytes = max_bytes
        self._log_identity: tuple[int, int] | None = None
        self._published: set[Path] = set()
        self._storage_guard = storage_guard

    @property
    def root(self) -> Path:
        return self._root

    @property
    def bytes_retained(self) -> int:
        """Count actual retained regular-file bytes, including interrupted staging."""
        try:
            _check_ancestry(self.root)
            if not self.root.is_dir():
                raise PrivateStorageError("private_storage_unsafe_path")
            total = 0
            for parent, directories, files in os.walk(self.root, onerror=_raise_os_error):
                for name in (*directories, *files):
                    entry = Path(parent) / name
                    details = entry.lstat()
                    if stat.S_ISLNK(details.st_mode):
                        raise PrivateStorageError("private_storage_unsafe_path")
                    if stat.S_ISREG(details.st_mode):
                        total += details.st_size
                    elif not stat.S_ISDIR(details.st_mode):
                        raise PrivateStorageError("private_storage_unsafe_path")
            return total
        except OSError:
            raise PrivateStorageError("private_storage_write_failed") from None

    def _reserve(self, additional_bytes: int) -> None:
        if self._storage_guard is not None:
            try:
                self._storage_guard(additional_bytes)
            except Exception:
                raise PrivateStorageError("private_storage_limit") from None
        if self.bytes_retained + additional_bytes > self._max_bytes:
            raise PrivateStorageError("private_storage_limit")

    def _new_target(self, relative: str) -> Path:
        logical = _relative_path(relative)
        if logical == _BUDGET_LOG or logical.is_relative_to(_BUDGET_LOG):
            raise PrivateStorageError("private_storage_unsafe_path")
        target = self.root / logical
        _check_ancestry(target)
        if target.exists() or any(target.is_relative_to(path) for path in self._published):
            raise PrivateStorageError("private_storage_exists")
        return target

    def write_bytes(self, relative: str, data: bytes) -> Path:
        """Create one immutable 0600 file and fsync it without overwriting."""
        if not isinstance(data, bytes):
            raise PrivateStorageError("private_storage_write_failed")
        try:
            target = self._new_target(relative)
            self._reserve(len(data))
            _make_directories(target.parent)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            with os.fdopen(os.open(target, flags, 0o600), "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return target
        except PrivateStorageError:
            raise
        except FileExistsError:
            raise PrivateStorageError("private_storage_exists") from None
        except OSError:
            raise PrivateStorageError("private_storage_write_failed") from None

    def append_event(self, event: Mapping[str, object]) -> None:
        """Append canonical compact JSONL only to this instance's own budget log."""
        try:
            data = (
                json.dumps(
                    dict(event),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            target = self.root / _BUDGET_LOG
            _check_ancestry(target)
            exists = target.exists()
            if exists and self._log_identity is None:
                raise PrivateStorageError("private_storage_exists")
            self._reserve(len(data))
            _make_directories(target.parent)
            flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW
            if not exists:
                flags |= os.O_CREAT | os.O_EXCL
            with os.fdopen(os.open(target, flags, 0o600), "ab") as stream:
                details = os.fstat(stream.fileno())
                identity = (details.st_dev, details.st_ino)
                if not stat.S_ISREG(details.st_mode) or (exists and identity != self._log_identity):
                    raise PrivateStorageError("private_storage_unsafe_path")
                if not exists:
                    os.fchmod(stream.fileno(), 0o600)
                    self._log_identity = identity
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except PrivateStorageError:
            raise
        except (OSError, TypeError, ValueError):
            raise PrivateStorageError("private_storage_write_failed") from None

    def publish(self, relative: str, deterministic: Mapping[str, bytes], runtime: bytes) -> Path:
        """Reserve the exact staged publication bytes, then reuse atomic publication."""
        try:
            target = self._new_target(relative)
            if _BUDGET_LOG.is_relative_to(_relative_path(relative)):
                raise PrivateStorageError("private_storage_unsafe_path")
            files = dict(deterministic)
            if not isinstance(runtime, bytes) or any(
                not isinstance(v, bytes) for v in files.values()
            ):
                raise PrivateStorageError("private_storage_write_failed")
            paths = {_relative_path(name) for name in files}
            reserved = {Path("hashes.json"), Path("runtime.json")}
            if paths & reserved:
                raise PrivateStorageError("private_storage_unsafe_path")
            paths |= reserved
            if any(parent in paths for path in paths for parent in path.parents):
                raise PrivateStorageError("private_storage_unsafe_path")
            hashes = canonical_json(
                {"schema_version": "research-hashes/v1", "sha256": content_hashes(files)}
            )
            self._reserve(sum(map(len, files.values())) + len(hashes) + len(runtime))
            _make_directories(target.parent)
            # This process-local mask is scoped to the declared sequential writer.
            # It makes the reused publisher's new nested paths private from creation.
            previous_mask = os.umask(0o077)
            try:
                publish_artifacts(target, files, runtime)
            finally:
                os.umask(previous_mask)
            self._published.add(target)
            return target
        except PrivateStorageError:
            raise
        except FileExistsError:
            raise PrivateStorageError("private_storage_exists") from None
        except (OSError, TypeError, ValueError):
            raise PrivateStorageError("private_storage_write_failed") from None


def _raise_os_error(error: OSError) -> None:
    raise error
