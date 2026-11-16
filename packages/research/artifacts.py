"""Canonical serialization and atomic publication of immutable research directories."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def canonical_csv(fields: Sequence[str], records: Sequence[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in records:
        # JSON encodes structured cells without platform-dependent repr or delimiter ambiguity.
        writer.writerow(
            {
                key: (
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                    if isinstance(value, (tuple, list, dict))
                    else value
                )
                for key, value in record.items()
            }
        )
    return stream.getvalue().encode("utf-8")


def content_hashes(files: Mapping[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}


def publish_artifacts(output: Path, deterministic: Mapping[str, bytes], runtime: bytes) -> None:
    """Stage siblings on the same filesystem; a cooperative exclusive lock prevents run races.

    An existing destination is always refused. Exceptions before rename leave no final run.
    Abrupt process death may leave a hidden staging directory/lock for manual inspection.
    """
    for name in deterministic:
        path = Path(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or name in {"hashes.json", "runtime.json"}
        ):
            raise ValueError(f"invalid_artifact_path:{name}")
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / f".{output.name}.lock"
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stage: Path | None = None
    try:
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"output_exists: {output.name}")
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
        files = dict(deterministic)
        files["hashes.json"] = canonical_json(
            {"schema_version": "research-hashes/v1", "sha256": content_hashes(files)}
        )
        files["runtime.json"] = runtime
        for name, data in sorted(files.items()):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        for directory in sorted(
            (p for p in stage.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
        ):
            _sync_directory(directory)
        _sync_directory(stage)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"output_exists: {output.name}")
        stage.rename(output)
        stage = None
        _sync_directory(output.parent)
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        os.close(lock_fd)
        lock.unlink()


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
