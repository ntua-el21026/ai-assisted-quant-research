"""Original synthetic private-candidate evidence; never provider observations."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from packages.data.alpaca_historical import HistoricalBarsRequest, historical_query


def _module():
    return importlib.import_module("packages.data.historical_candidates")


def candidate_fixture(tmp_path: Path, *, kind: str = "synthetic") -> Path:
    """Two invented sessions, exact invented prices and private receipt metadata."""
    root = tmp_path / "candidate"
    root.mkdir()
    request = HistoricalBarsRequest(
        provider="alpaca",
        symbols=("SYN",),
        start="2024-03-11",
        end="2024-03-12",
        feed="iex",
        adjustment="raw",
        timeframe="1Day",
    )
    _, query = historical_query(request)
    body = json.dumps(
        {
            "bars": {
                "SYN": [
                    {
                        "t": "2024-03-11T04:00:00Z",
                        "o": "12",
                        "h": "14",
                        "l": "11",
                        "c": "13",
                        "v": 100,
                    },
                    {
                        "t": "2024-03-12T04:00:00Z",
                        "o": "13",
                        "h": "15",
                        "l": "12",
                        "c": "14",
                        "v": 200,
                    },
                ]
            },
            "next_page_token": None,
        }
    ).encode()
    (root / "page.json").write_bytes(body)
    evidence = {
        "status": "confirmed",
        "source_refs": ["original-synthetic-evidence"],
        "statement": "Original synthetic engineering attestation.",
    }
    manifest = {
        "schema_version": "historical-candidate/v1",
        "kind": kind,
        "candidate_id": "synthetic-private-candidate",
        "frozen_at": "2024-03-14T13:00:00Z",
        "feed": "iex",
        "symbols": ["SYN"],
        "start": "2024-03-11",
        "end": "2024-03-12",
        "sessions": [
            {
                "date": day,
                "open_at": day + "T13:30:00Z",
                "close_at": day + "T20:00:00Z",
                "early_close": False,
            }
            for day in ("2024-03-11", "2024-03-12")
        ],
        "calendar_evidence": evidence,
        "license": {
            "name": "Original synthetic fixture",
            "reference": "original-author",
            **{
                key: "confirmed"
                for key in (
                    "entitlement",
                    "storage",
                    "retention",
                    "raw_redistribution",
                    "derived_publication",
                )
            },
            "restrictions": ["synthetic engineering only"],
        },
        "availability": {
            "mode": "synthetic" if kind == "synthetic" else "observed",
            "statement": "Original synthetic timestamps.",
            "evidence_reference": "original-author",
        },
        "identities": [
            {
                "security_id": "synthetic:001",
                "mappings": [
                    {
                        "symbol": "SYN",
                        "start": "2024-03-11",
                        "end": "2024-03-12",
                        "source": "original-author",
                        "available_at": "2024-03-10T12:00:00Z",
                        "availability_basis": "synthetic" if kind == "synthetic" else "observed",
                        "point_in_time_status": "confirmed",
                    }
                ],
            }
        ],
        "action_inventory": evidence,
        "reconciliation": evidence,
        "revision": {
            "revision_id": "original-synthetic",
            "parent_manifest_sha256": None,
            "correction_observed_at": None,
            "reason": "Original synthetic construction",
        },
        "files": [
            {
                "path": "page.json",
                "role": "raw_page",
                "acquisition_id": "bars-1",
                "size_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        ],
        "acquisitions": [
            {
                "acquisition_id": "bars-1",
                "role": "candidate",
                "request_kind": "bars",
                "request": request.model_dump(mode="json"),
                "request_started_at": "2024-03-13T12:00:00Z",
                "acquired_at": "2024-03-13T12:01:00Z",
                "pages": [
                    {
                        "file_path": "page.json",
                        "query": sorted(query.items()),
                        "received_at": "2024-03-13T12:01:00Z",
                        "http_status": 200,
                    }
                ],
                "complete": True,
            }
        ],
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def rewrite_manifest(path: Path, mutate) -> None:
    data = json.loads(path.read_bytes())
    mutate(data)
    path.write_text(json.dumps(data))


def replace_page(path: Path, value: object) -> None:
    body = json.dumps(value).encode()
    (path.parent / "page.json").write_bytes(body)

    def update(data):
        data["files"][0].update(size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest())

    rewrite_manifest(path, update)


def test_loader_preserves_exact_bytes_and_incomplete_research_evidence(tmp_path: Path) -> None:
    path = candidate_fixture(tmp_path, kind="historical")
    rewrite_manifest(path, lambda d: d["license"].update(retention="requires_clarification"))
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    candidate = _module().load_historical_candidate(path)
    assert candidate.files["page.json"] == before["page.json"]
    assert candidate.acquisitions[0].pages[0].body == before["page.json"]
    assert candidate.manifest.license.retention == "requires_clarification"
    assert before == {p.name: p.read_bytes() for p in path.parent.iterdir()}
    with pytest.raises(TypeError):
        candidate.files["page.json"] = b"changed"


@pytest.mark.parametrize(
    "mode,code",
    [
        ("hash", "candidate_hash_mismatch"),
        ("size", "candidate_size_mismatch"),
        ("missing", "candidate_missing_file"),
        ("extra", "candidate_inventory_mismatch"),
        ("symlink", "candidate_unsafe_path"),
        ("traversal", "invalid_candidate_manifest"),
    ],
)
def test_candidate_integrity_cannot_be_relaxed_for_diagnostics(
    tmp_path: Path,
    mode: str,
    code: str,
) -> None:
    path = candidate_fixture(tmp_path)
    if mode == "hash":
        rewrite_manifest(path, lambda d: d["files"][0].update(sha256="0" * 64))
    elif mode == "size":
        rewrite_manifest(path, lambda d: d["files"][0].update(size_bytes=1))
    elif mode == "missing":
        (path.parent / "page.json").unlink()
    elif mode == "extra":
        (path.parent / "unlisted.json").write_bytes(b"{}")
    elif mode == "symlink":
        target = tmp_path / "outside.json"
        (path.parent / "page.json").rename(target)
        (path.parent / "page.json").symlink_to(target)
    else:
        rewrite_manifest(path, lambda d: d["files"][0].update(path="../page.json"))
    with pytest.raises(ValueError, match=code):
        _module().load_historical_candidate(path)


def test_manifest_pin_precedes_observation_read(tmp_path: Path, monkeypatch) -> None:
    path = candidate_fixture(tmp_path)
    original = Path.read_bytes

    def read(file):
        if file.name == "page.json":
            pytest.fail("read before pin")
        return original(file)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ValueError, match="candidate_manifest_hash_mismatch"):
        _module().load_historical_candidate(path, expected_sha256="0" * 64)


def test_partial_failure_retains_error_response_without_faking_a_success_page(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    replace_page(path, {"message": "invented provider detail must remain private"})

    def change(data):
        data["acquisitions"][0].update(complete=False, error_code="forbidden")
        data["acquisitions"][0]["pages"][0]["http_status"] = 403

    rewrite_manifest(path, change)
    candidate = _module().load_historical_candidate(path)
    assert candidate.acquisitions[0].pages == ()
    assert b"invented provider detail" in candidate.files["page.json"]
    assert not candidate.manifest.acquisitions[0].complete


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["acquisitions"][0].update(error_code="provider secret leaked"),
        lambda d: d["acquisitions"][0].update(complete=False),
        lambda d: d["acquisitions"][0]["pages"][0].update(received_at="2024-03-13T12:02:00Z"),
        lambda d: d["acquisitions"][0].update(request_kind="actions"),
        lambda d: d["files"][0].update(acquisition_id="unknown"),
        lambda d: d["calendar_evidence"].update(source_refs=[]),
    ],
)
def test_contradictory_or_unbounded_provenance_is_rejected(tmp_path: Path, mutate) -> None:
    path = candidate_fixture(tmp_path)
    rewrite_manifest(path, mutate)
    with pytest.raises(ValueError, match="invalid_candidate_manifest"):
        _module().load_historical_candidate(path)


def test_malformed_page_is_preserved_for_the_qualification_layer(tmp_path: Path) -> None:
    path = candidate_fixture(tmp_path)
    raw = b'{"bars": {"SYN": [broken]}}'
    (path.parent / "page.json").write_bytes(raw)
    rewrite_manifest(
        path,
        lambda d: d["files"][0].update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
    )
    assert _module().load_historical_candidate(path).files["page.json"] == raw
