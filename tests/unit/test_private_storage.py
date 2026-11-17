"""Synthetic private storage enforces ignored scope, immutable writes, and byte caps."""

from __future__ import annotations

import hashlib
import importlib
import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

from packages.research.artifacts import canonical_json, content_hashes


def storage_module() -> Any:
    try:
        return importlib.import_module("packages.data.private_storage")
    except ModuleNotFoundError:
        pytest.fail("private storage is not implemented")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    (repository / ".gitignore").write_text("/datasets/**\n", encoding="utf-8")
    return repository


def new_storage(repository: Path, **kwargs: object) -> Any:
    return storage_module().PrivateStorage(
        repository / "datasets/private/r4b/attempt", repository, **kwargs
    )


def assert_code(exc: pytest.ExceptionInfo[Any], expected: str) -> None:
    assert exc.value.code == expected
    assert str(exc.value) == expected


def test_fresh_ignored_workspace_and_exclusive_files_have_private_modes(repository: Path) -> None:
    store = new_storage(repository)
    assert store.root == repository / "datasets/private/r4b/attempt"
    target = store.write_bytes("capture/page.json", b'{"synthetic":true}')
    assert target.read_bytes() == b'{"synthetic":true}'
    assert store.bytes_retained == 18
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE((repository / ".gitignore").stat().st_mode) == 0o644
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.write_bytes("capture/page.json", b"replacement")
    assert_code(exc, "private_storage_exists")
    assert target.read_bytes() == b'{"synthetic":true}'


def test_missing_ignore_coverage_fails_before_creating_workspace(repository: Path) -> None:
    module = storage_module()
    (repository / ".gitignore").write_text("", encoding="utf-8")
    workspace = repository / "datasets/private/r4b/attempt"
    with pytest.raises(module.PrivateStorageError) as exc:
        module.PrivateStorage(workspace, repository)
    assert_code(exc, "private_storage_path")
    assert not (repository / "datasets").exists()


def test_workspace_cannot_escape_private_subtree(repository: Path) -> None:
    module = storage_module()
    with pytest.raises(module.PrivateStorageError) as exc:
        module.PrivateStorage(repository / "datasets/public/attempt", repository)
    assert_code(exc, "private_storage_path")
    assert not (repository / "datasets").exists()


def test_existing_workspace_is_preserved(repository: Path) -> None:
    first = new_storage(repository)
    target = first.write_bytes("keep.txt", b"original")
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        new_storage(repository)
    assert_code(exc, "private_storage_exists")
    assert target.read_bytes() == b"original"


@pytest.mark.parametrize("limit", [-1, 1024**3 + 1, True])
def test_invalid_storage_limits_fail_without_creation(repository: Path, limit: object) -> None:
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        new_storage(repository, max_bytes=limit)
    assert_code(exc, "private_storage_limit")
    assert not (repository / "datasets").exists()


def test_exact_file_cap_rejects_excess_before_writing(repository: Path) -> None:
    store = new_storage(repository, max_bytes=4)
    store.write_bytes("first", b"1234")
    assert store.bytes_retained == 4
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.write_bytes("second", b"x")
    assert_code(exc, "private_storage_limit")
    assert not (store.root / "second").exists()
    assert store.bytes_retained == 4


@pytest.mark.parametrize("relative", ["../escape", "/escape", "a/../b", ".", "", "a//b", "a\\b"])
def test_unsafe_relative_paths_fail(repository: Path, relative: str) -> None:
    store = new_storage(repository)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.write_bytes(relative, b"synthetic")
    assert_code(exc, "private_storage_unsafe_path")
    assert store.bytes_retained == 0


def test_symlinked_workspace_parent_fails_before_creation(repository: Path, tmp_path: Path) -> None:
    module = storage_module()
    (repository / "datasets/private").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / "datasets/private/r4b").symlink_to(outside, target_is_directory=True)
    with pytest.raises(module.PrivateStorageError) as exc:
        new_storage(repository)
    assert_code(exc, "private_storage_unsafe_path")
    assert list(outside.iterdir()) == []


def test_symlinked_write_parent_cannot_touch_outside_files(
    repository: Path, tmp_path: Path
) -> None:
    store = new_storage(repository)
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.write_bytes("link/escape", b"synthetic")
    assert_code(exc, "private_storage_unsafe_path")
    assert list(outside.iterdir()) == []


def test_canonical_budget_log_is_the_only_appendable_file(repository: Path) -> None:
    store = new_storage(repository)
    frozen = store.write_bytes("capture/frozen", b"immutable")
    store.append_event({"z": 2, "a": "synthetic"})
    log = store.root / "runtime/budget.jsonl"
    assert log.read_bytes() == b'{"a":"synthetic","z":2}\n'
    store.append_event({"next": True})
    assert log.read_bytes() == b'{"a":"synthetic","z":2}\n{"next":true}\n'
    assert frozen.read_bytes() == b"immutable"
    assert store.bytes_retained == len(frozen.read_bytes()) + len(log.read_bytes())
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.parent.stat().st_mode) == 0o700
    with pytest.raises(storage_module().PrivateStorageError):
        store.write_bytes("runtime/budget.jsonl", b"replace")


def test_append_rejects_cap_before_changing_existing_log(repository: Path) -> None:
    store = new_storage(repository, max_bytes=6)
    store.append_event({})
    log = store.root / "runtime/budget.jsonl"
    assert log.read_bytes() == b"{}\n"
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.append_event({"x": 1})
    assert_code(exc, "private_storage_limit")
    assert log.read_bytes() == b"{}\n"


def test_append_will_not_modify_an_unowned_preexisting_file(repository: Path) -> None:
    store = new_storage(repository)
    (store.root / "runtime").mkdir()
    log = store.root / "runtime/budget.jsonl"
    log.write_bytes(b"external")
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.append_event({})
    assert_code(exc, "private_storage_exists")
    assert log.read_bytes() == b"external"


def test_publication_reserves_exact_metadata_runtime_and_payload_bytes(repository: Path) -> None:
    module = storage_module()
    deterministic = {"result.json": b'{"synthetic":true}\n', "nested/data.txt": b"abc"}
    runtime = b'{"attempt":1}\n'
    hashes = canonical_json(
        {"schema_version": "research-hashes/v1", "sha256": content_hashes(deterministic)}
    )
    publication_size = sum(map(len, deterministic.values())) + len(runtime) + len(hashes)
    store = new_storage(repository, max_bytes=publication_size + 4)
    store.write_bytes("capture/raw", b"wire")
    output = store.publish("qualified/attempt", deterministic, runtime)
    assert store.bytes_retained == publication_size + 4
    assert (output / "hashes.json").read_bytes() == hashes
    assert (output / "runtime.json").read_bytes() == runtime
    assert json.loads(hashes)["sha256"]["nested/data.txt"] == hashlib.sha256(b"abc").hexdigest()
    for entry in (output, *output.rglob("*")):
        assert stat.S_IMODE(entry.stat().st_mode) == (0o700 if entry.is_dir() else 0o600)
    with pytest.raises(module.PrivateStorageError) as exc:
        store.publish("qualified/attempt", deterministic, runtime)
    assert_code(exc, "private_storage_exists")


def test_publication_one_byte_over_cap_creates_no_output(repository: Path) -> None:
    deterministic = {"sample": b"abc"}
    hashes = canonical_json(
        {"schema_version": "research-hashes/v1", "sha256": content_hashes(deterministic)}
    )
    store = new_storage(repository, max_bytes=len(hashes) + 3)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.publish("candidate", deterministic, b"x")
    assert_code(exc, "private_storage_limit")
    assert not (store.root / "candidate").exists()
    assert list(store.root.iterdir()) == []


def test_publication_creates_private_modes_before_wrapper_postprocessing(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = storage_module()
    store = new_storage(repository)
    real_publish = module.publish_artifacts
    observed: dict[str, int] = {}

    def inspect_publication(output: Path, deterministic: dict[str, bytes], runtime: bytes) -> None:
        real_publish(output, deterministic, runtime)
        for entry in (output, *output.rglob("*")):
            observed[str(entry.relative_to(output))] = stat.S_IMODE(entry.stat().st_mode)

    monkeypatch.setattr(module, "publish_artifacts", inspect_publication)
    store.publish("candidate", {"nested/data": b"synthetic"}, b"{}")
    assert observed == {
        ".": 0o700,
        "nested": 0o700,
        "nested/data": 0o600,
        "hashes.json": 0o600,
        "runtime.json": 0o600,
    }


def test_publication_rejects_ancestor_file_conflicts_before_writing(repository: Path) -> None:
    store = new_storage(repository)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.publish("candidate", {"a": b"one", "a/b": b"two"}, b"{}")
    assert_code(exc, "private_storage_unsafe_path")
    assert store.bytes_retained == 0


@pytest.mark.parametrize("operation", ["write", "publish"])
def test_published_directory_cannot_gain_new_files(repository: Path, operation: str) -> None:
    store = new_storage(repository)
    output = store.publish("candidate", {"sample": b"abc"}, b"{}")
    before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        if operation == "write":
            store.write_bytes("candidate/addition", b"new")
        else:
            store.publish("candidate/nested", {"new": b"new"}, b"{}")
    assert_code(exc, "private_storage_exists")
    after = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("name", ["hashes.json", "runtime.json", "../escape"])
def test_publication_rejects_reserved_and_escaping_payload_names(
    repository: Path, name: str
) -> None:
    store = new_storage(repository)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.publish("candidate", {name: b"synthetic"}, b"{}")
    assert_code(exc, "private_storage_unsafe_path")
    assert list(store.root.iterdir()) == []


def test_failed_fsync_reports_closed_code_and_counts_retained_bytes(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = storage_module()
    store = new_storage(repository, max_bytes=3)

    def fail_fsync(fd: int) -> None:
        raise OSError("synthetic private detail")

    monkeypatch.setattr(module.os, "fsync", fail_fsync)
    with pytest.raises(module.PrivateStorageError) as exc:
        store.write_bytes("partial", b"abc")
    assert_code(exc, "private_storage_write_failed")
    assert store.bytes_retained == 3
    assert stat.S_IMODE((store.root / "partial").stat().st_mode) == 0o600


def test_actual_retained_bytes_include_files_created_outside_writer(repository: Path) -> None:
    store = new_storage(repository, max_bytes=5)
    (store.root / "existing").write_bytes(b"12345")
    assert store.bytes_retained == 5
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.write_bytes("new", b"x")
    assert_code(exc, "private_storage_limit")


def test_unserializable_budget_events_fail_without_a_log(repository: Path) -> None:
    store = new_storage(repository)
    with pytest.raises(storage_module().PrivateStorageError) as exc:
        store.append_event({"unsupported": object()})
    assert_code(exc, "private_storage_write_failed")
    assert store.bytes_retained == 0
