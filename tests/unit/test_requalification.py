"""Synthetic requalification binds evidence without admitting historical research data."""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_acquisition_session import Clock, SyntheticTransport, run

from packages.data.acquisition_session import acquire_registered_candidate
from packages.data.historical_candidates import load_historical_candidate
from packages.data.historical_qualification import qualify_historical_candidate
from packages.research.artifacts import canonical_json


def api() -> Any:
    try:
        return importlib.import_module("packages.data.requalification")
    except ModuleNotFoundError:
        pytest.fail("requalification implementation missing")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_policy(tmp_path: Path, *, original_special: bool = True) -> tuple[Path, Path]:
    result, _, workspace = run(tmp_path, special_preflight=original_special)
    repository = workspace.parents[3]
    manifest = json.loads(result.manifest_path.read_bytes())
    if original_special:
        entry = next(
            f
            for f in manifest["files"]
            if f["role"] == "raw_page" and f["acquisition_id"] == "preflight-actions"
        )
        source = result.manifest_path.parent / entry["path"]
        payload = json.loads(source.read_bytes())
        row = payload["corporate_actions"]["cash_dividends"][0]
        row.update(
            id="synthetic-private-special-id",
            rate="9.125",
            ex_date="2023-12-11",
            payable_date="2024-01-16",
            currency="USD",
        )
        source.write_bytes(canonical_json(payload))
        entry.update(size_bytes=source.stat().st_size, sha256=digest(source))
        result.manifest_path.write_bytes(canonical_json(manifest))
    original = load_historical_candidate(result.manifest_path)
    qualification = workspace / "original-qualification.json"
    qualification.write_bytes(
        canonical_json(qualify_historical_candidate(original).model_dump(mode="json"))
    )
    configs = repository / "experiments/configs"
    configs.mkdir(parents=True)
    calendar = configs / "calendar.json"
    calendar.write_bytes(Path("experiments/configs/r4b_calendar_2020_2025.json").read_bytes())
    plan = json.loads(Path("experiments/configs/r4b_acquisition.json").read_bytes())
    plan["calendar_path"] = "calendar.json"
    plan["stages"] = [s for s in plan["stages"] if s["role"] != "diagnostic"]
    plan_path = configs / "plan.json"
    plan_path.write_bytes(canonical_json(plan))
    evidence = repository / "datasets/private/r4b/issuer"
    evidence.mkdir()
    independent = evidence / "independent.json"
    independent.write_bytes(b"[]\n")
    flagged = evidence / "flagged.json"
    flagged.write_bytes(
        canonical_json(
            {
                "economic_equalities": {"pay_date_equal": False},
                "currency_independently_established": False,
                "provider_special_flag_preserved": True,
                "provider_record": {"id": "synthetic-private-special-id", "rate": "9.125"},
            }
        )
    )
    index = evidence / "index.json"
    index.write_bytes(
        canonical_json(
            {
                "files": {
                    p.name: {"size_bytes": p.stat().st_size, "sha256": digest(p)}
                    for p in [independent, flagged]
                }
            }
        )
    )

    def scope(start: str) -> dict[str, object]:
        return {
            "start": start,
            "end": "2025-12-31",
            "feature_history_start": start,
            "opening_state": "flat_cash",
            "raw_execution": True,
            "feature_basis": "raw",
            "opening_positions_empty": True,
            "opening_orders_empty": True,
            "opening_receivables_empty": True,
            "opening_balances_independent": True,
        }

    policy = {
        "schema_version": "historical-requalification-policy/v1",
        "checkpoint": "R4-B.1",
        "issuer_indexes": [{"path": str(index.relative_to(repository)), "sha256": digest(index)}],
        "pilot_scope": scope("2024-01-01"),
        "candidate_scope": scope("2020-01-01"),
    }
    for name, path in {
        "plan": plan_path,
        "original_manifest": result.manifest_path,
        "original_qualification": qualification,
        "seed_events": workspace / "runtime/budget.jsonl",
        "independent_actions": independent,
        "flagged_event_evidence": flagged,
    }.items():
        policy[name + "_path"] = str(path.relative_to(repository))
        policy[name + "_sha256"] = digest(path)
    policy_path = configs / "policy.json"
    policy_path.write_bytes(canonical_json(policy))
    return policy_path, repository


def test_loader_pins_policy_original_and_all_indexed_evidence(tmp_path: Path) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    assert isinstance(inputs, module.RequalificationInputs)
    assert inputs.sha256 == digest(path) and inputs.raw_bytes == path.read_bytes()
    assert inputs.original.manifest_sha256 == inputs.policy.original_manifest_sha256
    assert not inputs.independent_actions
    assert inputs.policy.plan_path in inputs.evidence_hashes
    assert inputs.original_qualification["status"] == "FAIL"


@pytest.mark.parametrize(
    "mutation", ["direct_hash", "indexed_hash", "index_escape", "symlink", "scope_shrink"]
)
def test_loader_rejects_changed_unsafe_or_misbound_evidence(tmp_path: Path, mutation: str) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    policy = json.loads(path.read_bytes())
    if mutation == "direct_hash":
        policy["independent_actions_sha256"] = "0" * 64
    elif mutation == "indexed_hash":
        (repository / policy["flagged_event_evidence_path"]).write_bytes(b"{}\n")
    elif mutation == "index_escape":
        index = repository / policy["issuer_indexes"][0]["path"]
        value = json.loads(index.read_bytes())
        value["files"]["../escape"] = {"sha256": "a" * 64, "size_bytes": 0}
        index.write_bytes(canonical_json(value))
        policy["issuer_indexes"][0]["sha256"] = digest(index)
    elif mutation == "symlink":
        source = repository / policy["independent_actions_path"]
        copy = source.with_name("copy.json")
        copy.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(copy)
    else:
        policy["candidate_scope"]["start"] = "2024-01-01"
        policy["candidate_scope"]["feature_history_start"] = "2024-01-01"
    path.write_bytes(canonical_json(policy))
    with pytest.raises(ValueError, match="requalification_"):
        module.load_requalification_inputs(path, repository)


def test_scope_evaluator_retains_special_evidence_and_preserves_original_bytes(
    tmp_path: Path,
) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    evaluate = module.make_action_evaluator(inputs)
    source = inputs.original.acquisitions[1]
    before = source.pages[0].body
    stage = inputs.registered.plan.stages[1]
    prior = evaluate(stage, source, {"SPY": "research:SPY", "QQQ": "research:QQQ"})
    assert prior.error_code is None and prior.actions == ()
    assert json.loads(prior.evidence["scope-summary.json"])["outside_count"] == 1
    assert json.loads(prior.evidence["scope-private.json"])["records"][0]["special"] is True
    relevant = evaluate(
        stage.model_copy(update={"role": "candidate"}), source, {"SPY": "research:SPY"}
    )
    assert relevant.error_code == "unsupported_corporate_action"
    assert json.loads(relevant.evidence["scope-summary.json"])["blocked"] is True
    assert source.pages[0].body == before


def test_pilot_gate_blocks_larger_queries_for_known_candidate_period_special(
    tmp_path: Path,
) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    transport, clock = SyntheticTransport(inputs.registered), Clock()
    result = acquire_registered_candidate(
        inputs.registered,
        repository=repository,
        workspace=repository / "datasets/private/r4b/requalified",
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        reused_acquisitions={
            s.acquisition_id: a
            for s, a in zip(
                inputs.registered.plan.stages[:2], inputs.original.acquisitions[:2], strict=True
            )
        },
        action_evaluator=module.make_action_evaluator(inputs),
        pilot_gate=module.make_pilot_gate(inputs),
    )
    candidate = load_historical_candidate(result.manifest_path)
    assert len(transport.calls) == 2
    assert not result.pilot_passed
    assert not any(record.role == "candidate" for record in candidate.manifest.acquisitions)
    report = module.build_requalification_report(candidate, inputs)
    assert report["technical_pilot"]["status"] == "PASS"
    assert report["base_qualification"]["status"] == "FAIL"
    assert report["original_qualification"] == inputs.original_qualification
    assert report["scientific_readiness"]["decision"] == "BLOCKED"
    assert report["admitted_v2"] is False
    encoded = canonical_json(report)
    assert b"synthetic-private-special-id" not in encoded
    assert b"9.125" not in encoded
    assert encoded == canonical_json(module.build_requalification_report(candidate, inputs))


def test_clean_technical_pilot_still_requires_complete_independent_reconciliation(
    tmp_path: Path,
) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path, original_special=False)
    inputs = module.load_requalification_inputs(path, repository)
    transport, clock = SyntheticTransport(inputs.registered), Clock()
    result = acquire_registered_candidate(
        inputs.registered,
        repository=repository,
        workspace=repository / "datasets/private/r4b/clean",
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        action_evaluator=module.make_action_evaluator(inputs),
    )
    candidate = load_historical_candidate(result.manifest_path)
    gate = module.make_pilot_gate(inputs)
    report = module.build_requalification_report(candidate, inputs)
    assert report["technical_pilot"]["status"] == "PASS"
    assert report["ordinary_action_reconciliation"]["status"] == "RESTRICTED"
    assert gate(candidate.manifest.acquisitions, candidate.files) is False
    pilot_bar = next(
        record
        for record in candidate.manifest.acquisitions
        if record.role == "pilot" and record.request_kind == "bars"
    )
    changed = dict(candidate.files)
    changed.pop(pilot_bar.pages[0].file_path)
    assert gate(candidate.manifest.acquisitions, changed) is False


def test_malformed_source_returns_closed_error_with_scope_evidence(tmp_path: Path) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    stage = inputs.registered.plan.stages[1]
    source = inputs.original.acquisitions[1]
    malformed = replace(
        source,
        pages=(
            replace(source.pages[0], body=b'{"corporate_actions":false,"next_page_token":null}'),
        ),
    )
    result = module.make_action_evaluator(inputs)(stage, malformed, {})
    assert result.error_code == "invalid_corporate_action"
    assert result.actions == ()
    assert json.loads(result.evidence["scope-summary.json"])["blocked"] is True


def test_returned_report_cannot_mutate_the_pinned_original_qualification(tmp_path: Path) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    expected = canonical_json(dict(inputs.original_qualification))
    report = module.build_requalification_report(inputs.original, inputs)
    report["original_qualification"]["findings"].clear()
    assert canonical_json(dict(inputs.original_qualification)) == expected
    assert (
        canonical_json(
            module.build_requalification_report(inputs.original, inputs)["original_qualification"]
        )
        == expected
    )


def test_blocked_scope_defers_reconciliation_without_false_missing_provider_counts(
    tmp_path: Path,
) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path)
    inputs = module.load_requalification_inputs(path, repository)
    transport = SyntheticTransport(inputs.registered, unsupported_pilot_action=True)
    clock = Clock()
    result = acquire_registered_candidate(
        inputs.registered,
        repository=repository,
        workspace=repository / "datasets/private/r4b/blocked-pilot",
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        reused_acquisitions={
            stage.acquisition_id: source
            for stage, source in zip(
                inputs.registered.plan.stages[:2], inputs.original.acquisitions[:2], strict=True
            )
        },
        action_evaluator=module.make_action_evaluator(inputs),
    )
    candidate = load_historical_candidate(result.manifest_path)
    report = module.build_requalification_report(candidate, inputs)
    reconciliation = report["ordinary_action_reconciliation"]
    assert reconciliation["available"] is False
    assert reconciliation["status"] == "RESTRICTED"
    assert reconciliation["reason"] == "pilot_scope_or_normalization_blocks_reconciliation"
    assert "missing_provider_count" not in reconciliation
    assert report["technical_pilot"]["status"] == "FAIL"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("error_query", "FAIL"),
        ("duplicate_error_query", "FAIL"),
        ("error_status", "FAIL"),
        ("error_time", "FAIL"),
        ("missing_error_body", "FAIL"),
        ("error_after_terminal_success", "FAIL"),
        ("valid_retry", "PASS"),
    ],
)
def test_technical_pilot_validates_error_pages_before_success_projection(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    module = api()
    path, repository = fixture_policy(tmp_path, original_special=False)
    inputs = module.load_requalification_inputs(path, repository)
    candidate = inputs.original
    bar = next(
        record
        for record in candidate.manifest.acquisitions
        if record.role == "pilot" and record.request_kind == "bars"
    )
    error = bar.pages[0].model_copy(
        update={"file_path": "synthetic/error-page.json", "http_status": 429}
    )
    if mutation == "error_query":
        query = dict(error.query)
        query["feed"] = "sip"
        error = error.model_copy(update={"query": tuple(sorted(query.items()))})
    elif mutation == "duplicate_error_query":
        error = error.model_copy(update={"query": (*error.query, error.query[0])})
    elif mutation == "error_status":
        error = error.model_copy(update={"http_status": 403})
    elif mutation == "error_time":
        error = error.model_copy(update={"received_at": datetime(2020, 1, 1, tzinfo=UTC)})
    pages = (
        (*bar.pages, error) if mutation == "error_after_terminal_success" else (error, *bar.pages)
    )
    changed = bar.model_copy(update={"pages": pages})
    manifest = candidate.manifest.model_copy(
        update={
            "acquisitions": tuple(
                changed if record is bar else record for record in candidate.manifest.acquisitions
            )
        }
    )
    files = dict(candidate.files)
    if mutation != "missing_error_body":
        files[error.file_path] = b"invented retry response"
    report = module.build_requalification_report(
        replace(candidate, manifest=manifest, files=files), inputs
    )
    assert report["technical_pilot"]["status"] == expected
    if mutation in {"error_query", "error_after_terminal_success"}:
        assert report["base_qualification"]["status"] == "FAIL"
