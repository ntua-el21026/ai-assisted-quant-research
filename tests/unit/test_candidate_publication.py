"""Private candidate publication keeps envelope metadata outside exact evidence."""

from __future__ import annotations

import hashlib
import importlib
import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_historical_candidates import candidate_fixture

from packages.data.historical_candidates import CandidateManifest, load_historical_candidate
from packages.data.private_storage import PrivateStorage, PrivateStorageError
from packages.research.artifacts import canonical_json


def api() -> Any:
    return importlib.import_module("packages.data.candidate_publication")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    (repository / ".gitignore").write_text("/datasets/**\n", encoding="utf-8")
    return repository


def storage(repository: Path, name: str = "attempt", **options: Any) -> PrivateStorage:
    return PrivateStorage(repository / "datasets/private/r4b" / name, repository, **options)


def inputs(tmp_path: Path) -> tuple[CandidateManifest, dict[str, bytes]]:
    original = tmp_path / "original"
    original.mkdir()
    path = candidate_fixture(original)
    manifest = CandidateManifest.model_validate(json.loads(path.read_bytes()))
    return manifest, {file.path: (path.parent / file.path).read_bytes() for file in manifest.files}


def test_published_nested_evidence_loads_unchanged_and_has_private_modes(
    repository: Path, tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    store = storage(repository)
    published = api().publish_candidate(
        store, "candidates/primary", manifest, files, b'{"run":1}\n'
    )
    assert published == store.root / "candidates/primary/evidence/manifest.json"
    loaded = load_historical_candidate(published)
    assert loaded.manifest == manifest
    assert loaded.files == files
    assert published.read_bytes() == canonical_json(manifest.model_dump(mode="json"))
    outer = published.parent.parent
    assert {p.relative_to(outer).as_posix() for p in outer.rglob("*") if p.is_file()} == {
        "evidence/manifest.json", "evidence/page.json", "hashes.json", "runtime.json",
    }
    index = json.loads((outer / "hashes.json").read_bytes())
    assert index["sha256"] == {
        "evidence/manifest.json": hashlib.sha256(published.read_bytes()).hexdigest(),
        "evidence/page.json": hashlib.sha256(files["page.json"]).hexdigest(),
    }
    assert (outer / "runtime.json").read_bytes() == b'{"run":1}\n'
    for path in (outer, *outer.rglob("*")):
        assert stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)


def test_identical_inputs_publish_identical_deterministic_bytes_across_attempts(
    repository: Path, tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    first = api().publish_candidate(storage(repository, "one"), "candidate", manifest, files, b"1")
    second = api().publish_candidate(storage(repository, "two"), "candidate", manifest, files, b"2")
    def deterministic(path: Path) -> dict[str, bytes]:
        outer = path.parent.parent
        return {p.relative_to(outer).as_posix(): p.read_bytes() for p in outer.rglob("*")
                if p.is_file() and p.name != "runtime.json"}
    assert deterministic(first) == deterministic(second)


@pytest.mark.parametrize("mutation", ["missing", "extra", "size", "hash", "nonbytes"])
def test_invalid_payload_inventory_fails_before_creating_publication(
    repository: Path, tmp_path: Path, mutation: str,
) -> None:
    manifest, files = inputs(tmp_path)
    if mutation == "missing":
        files.clear()
    elif mutation == "extra":
        files["unrecorded.json"] = b"private"
    elif mutation == "size":
        files["page.json"] += b" "
    elif mutation == "hash":
        files["page.json"] = files["page.json"].replace(b'"o": "12"', b'"o": "99"')
    else:
        files["page.json"] = "private"  # type: ignore[assignment]
    store = storage(repository)
    with pytest.raises(api().CandidatePublicationError) as error:
        api().publish_candidate(store, "candidate", manifest, files, b"{}")
    assert str(error.value) == error.value.code
    assert "private" not in str(error.value)
    assert list(store.root.iterdir()) == []


@pytest.mark.parametrize("path", ["manifest.json", "manifest.json/child"])
def test_manifest_path_collisions_fail_before_any_writes(
    repository: Path, tmp_path: Path, path: str,
) -> None:
    manifest, files = inputs(tmp_path)
    data = manifest.model_dump(mode="json")
    data["files"][0]["path"] = path
    data["acquisitions"][0]["pages"][0]["file_path"] = path
    changed = CandidateManifest.model_validate(data)
    store = storage(repository)
    with pytest.raises(api().CandidatePublicationError, match="candidate_publication_path"):
        api().publish_candidate(store, "candidate", changed, {path: files["page.json"]}, b"{}")
    assert list(store.root.iterdir()) == []


def test_declared_ancestor_file_conflicts_fail_before_publication(
    repository: Path, tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    data = manifest.model_dump(mode="json")
    data["files"].append({"path": "page.json/child", "role": "evidence", "size_bytes": 1,
                          "sha256": hashlib.sha256(b"x").hexdigest()})
    changed = CandidateManifest.model_validate(data)
    store = storage(repository)
    with pytest.raises(api().CandidatePublicationError, match="candidate_publication_path"):
        api().publish_candidate(
            store, "candidate", changed, files | {"page.json/child": b"x"}, b"{}"
        )
    assert list(store.root.iterdir()) == []


def test_revalidates_manually_constructed_manifest_before_publication(
    repository: Path, tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    changed = manifest.model_copy(update={"feed": "boats"})
    store = storage(repository)
    with pytest.raises(api().CandidatePublicationError, match="candidate_publication_manifest"):
        api().publish_candidate(store, "candidate", changed, files, b"{}")
    assert list(store.root.iterdir()) == []


def test_private_storage_is_required_before_releasing_raw_candidate_bytes(
    tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    class PublicSink:
        def publish(self, *args: object) -> Path:
            pytest.fail("raw candidate bytes reached an unqualified writer")
    with pytest.raises(api().CandidatePublicationError, match="candidate_private_storage_required"):
        api().publish_candidate(PublicSink(), "candidate", manifest, files, b"{}")


def test_existing_candidate_is_immutable(repository: Path, tmp_path: Path) -> None:
    manifest, files = inputs(tmp_path)
    store = storage(repository)
    published = api().publish_candidate(store, "candidate", manifest, files, b"first")
    before = published.read_bytes()
    with pytest.raises(PrivateStorageError, match="private_storage_exists"):
        api().publish_candidate(store, "candidate", manifest, files, b"second")
    assert published.read_bytes() == before
    assert (published.parent.parent / "runtime.json").read_bytes() == b"first"


def test_storage_cap_counts_nested_manifest_index_runtime_and_raw_bytes(
    repository: Path, tmp_path: Path,
) -> None:
    manifest, files = inputs(tmp_path)
    raw_manifest = canonical_json(manifest.model_dump(mode="json"))
    payloads = {"evidence/manifest.json": raw_manifest, "evidence/page.json": files["page.json"]}
    index = canonical_json({"schema_version": "research-hashes/v1", "sha256": {
        name: hashlib.sha256(body).hexdigest() for name, body in payloads.items()
    }})
    exact_size = sum(map(len, payloads.values())) + len(index) + len(b"runtime")
    small = storage(repository, "small", max_bytes=exact_size - 1)
    with pytest.raises(PrivateStorageError, match="private_storage_limit"):
        api().publish_candidate(small, "candidate", manifest, files, b"runtime")
    assert list(small.root.iterdir()) == []
    exact = storage(repository, "exact", max_bytes=exact_size)
    api().publish_candidate(exact, "candidate", manifest, files, b"runtime")
    assert exact.bytes_retained == exact_size
