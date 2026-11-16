"""Hand-authored synthetic evidence checks software contracts, not AI efficacy."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from packages.research.models import ResearchDecision, ResearchSignalSet

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ai_replay"
CUTOFF = datetime(2026, 5, 4, 20, 1, tzinfo=UTC)


def _module() -> ModuleType:
    return importlib.import_module("packages.research.ai_replay")


def _signals() -> ResearchSignalSet:
    return ResearchSignalSet(
        decisions=(
            ResearchDecision(
                decision_id="accepted-aapl",
                symbol="AAPL",
                decision_session=date(2026, 5, 4),
                decision_at=CUTOFF,
                eligible_session=date(2026, 5, 5),
                accepted=True,
                quantity=7,
                reference_price=100,
                stop_price=95,
                breakout_level=99,
                reason_codes=("deterministic_candidate",),
            ),
            ResearchDecision(
                decision_id="rejected-aapl",
                symbol="AAPL",
                decision_session=date(2026, 5, 4),
                decision_at=CUTOFF,
                eligible_session=date(2026, 5, 5),
                accepted=False,
                quantity=4,
                reference_price=100,
                stop_price=95,
                reason_codes=("deterministic_risk_rejection",),
            ),
        )
    )


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE, tmp_path / "evidence")
    return tmp_path / "evidence" / "manifest.json"


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _repair(manifest_path: Path) -> None:
    manifest = _read(manifest_path)
    files = [manifest[key]["file"] for key in ("model", "prompt", "output_schema")]
    files += [article["file"] for article in manifest["articles"]]
    files += [record["output"] for record in manifest["records"] if record["output"]]
    for entry in files:
        path = manifest_path.parent / entry["path"]
        if path.exists():
            raw = path.read_bytes()
            entry.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    _write(manifest_path, manifest)


def _output(bundle: Path) -> Path:
    return bundle.parent / "negative-output.json"


def _replay(bundle: Path, *, neutral_control: bool = False) -> Any:
    module = _module()
    return module.replay_ai_evidence(
        _signals(), module.load_frozen_ai_evidence(bundle), CUTOFF, neutral_control=neutral_control
    )


def test_synthetic_negative_overlay_floors_size_and_preserves_deterministic_rejections(
    bundle: Path,
) -> None:
    module = _module()
    evidence = module.load_frozen_ai_evidence(bundle)
    original = _signals()
    result = module.apply_research_ai_overlay(original, evidence, CUTOFF)

    assert len(result.decisions) == 2
    assert result.decisions[0].quantity == 3  # floor(7 * 0.5), never rounding to four
    assert result.decisions[0].accepted
    assert result.decisions[1].model_dump_json() == original.decisions[1].model_dump_json()
    for field in (
        "decision_id",
        "symbol",
        "action",
        "decision_session",
        "decision_at",
        "eligible_session",
        "reference_price",
        "stop_price",
        "breakout_level",
    ):
        assert getattr(result.decisions[0], field) == getattr(original.decisions[0], field)
    assert evidence.manifest.kind == "synthetic"
    assert evidence.manifest_sha256 == hashlib.sha256(bundle.read_bytes()).hexdigest()


def test_neutral_control_exact_parity_and_serializable_diagnostics(bundle: Path) -> None:
    result = _replay(bundle, neutral_control=True)

    assert result.signals.model_dump_json() == _signals().model_dump_json()
    assert [row.decision_id for row in result.diagnostics] == ["accepted-aapl", "rejected-aapl"]
    assert result.diagnostics[0].reason == "neutral_control"
    assert result.diagnostics[1].reason == "deterministic_rejection_preserved"
    assert json.loads(result.model_dump_json())["diagnostics"][0]["original_quantity"] == 7


@pytest.mark.parametrize("missing", [True, False])
def test_missing_and_empty_evidence_are_neutral(bundle: Path, missing: bool) -> None:
    module = _module()
    if missing:
        bundle = bundle.parent / "absent.json"
        expected = "missing_evidence"
    else:
        manifest = _read(bundle)
        manifest["records"] = []
        _write(bundle, manifest)
        expected = "no_candidate_evidence"
    result = module.replay_ai_evidence(_signals(), module.load_frozen_ai_evidence(bundle), CUTOFF)

    assert result.signals.model_dump_json() == _signals().model_dump_json()
    assert result.diagnostics[0].reason == expected


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("malformed", "invalid_json"),
        ("schema", "schema_violation"),
        ("missing", "missing_output"),
        ("empty", "invalid_json"),
        ("provider_failure", "provider_failure"),
        ("fallback", "provider_error"),
    ],
)
def test_invalid_and_unavailable_outputs_fall_back_neutrally(
    bundle: Path, mutation: str, expected: str
) -> None:
    manifest = _read(bundle)
    output = _read(_output(bundle))
    if mutation == "malformed":
        _output(bundle).write_text("{broken-json")
    elif mutation == "schema":
        output["size_multiplier"] = 2
        _write(_output(bundle), output)
    elif mutation == "missing":
        _output(bundle).unlink()
    elif mutation == "empty":
        _output(bundle).write_text("")
    elif mutation == "provider_failure":
        manifest["records"][0]["provider_failure"] = {
            "symbol": "AAPL",
            "occurred_at": "2026-05-04T19:30:00Z",
            "provider": "synthetic",
            "reason": "provider_error",
            "message": "Hand-authored failure illustration",
        }
        _write(bundle, manifest)
    elif mutation == "fallback":
        output.update(fallback=True, fallback_reason="provider_error")
        _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert result.signals.model_dump_json() == _signals().model_dump_json()
    assert result.diagnostics[0].reason == expected
    assert result.diagnostics[0].fallback


@pytest.mark.parametrize("field", ["analysis_at", "output_available_at"])
def test_post_cutoff_analysis_or_output_cannot_affect_decision(bundle: Path, field: str) -> None:
    manifest = _read(bundle)
    manifest["records"][0][field] = "2026-05-05T20:00:00Z"
    if field == "analysis_at":
        manifest["records"][0]["output_available_at"] = "2026-05-05T20:00:01Z"
    _write(bundle, manifest)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "no_asof_evidence"


@pytest.mark.parametrize(
    ("target", "field", "expected"),
    [
        ("article", "published_at", "article_not_available"),
        ("manifest_article", "observed_available_at", "article_not_available"),
        ("citation", "published_at", "future_citation"),
        ("event", "published_at", "future_event"),
        ("output", "analysis_at", "output_metadata_mismatch"),
    ],
)
def test_future_article_citation_event_and_output_metadata_are_neutral(
    bundle: Path, target: str, field: str, expected: str
) -> None:
    manifest = _read(bundle)
    output = _read(_output(bundle))
    future = "2026-05-05T20:00:00Z"
    if target == "article":
        article_path = bundle.parent / "article.json"
        article = _read(article_path)
        article[field] = future
        manifest["articles"][0]["observed_available_at"] = future
        _write(article_path, article)
    elif target == "manifest_article":
        manifest["articles"][0][field] = future
    elif target == "output":
        output[field] = future
    else:
        output["citations" if target == "citation" else "events"][0][field] = future
    _write(bundle, manifest)
    _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].reason == expected


def test_each_candidate_uses_its_own_timestamp_even_with_later_global_cutoff(bundle: Path) -> None:
    manifest = _read(bundle)
    manifest["records"][0]["output_available_at"] = "2026-05-04T20:02:00Z"
    _write(bundle, manifest)
    module = _module()
    result = module.replay_ai_evidence(
        _signals(), module.load_frozen_ai_evidence(bundle), CUTOFF + timedelta(days=1)
    )

    assert result.signals == _signals()


@pytest.mark.parametrize("target", ["decision_id", "symbol", "decision_at"])
def test_evidence_is_bound_to_the_exact_candidate(bundle: Path, target: str) -> None:
    manifest = _read(bundle)
    manifest["records"][0][target] = {
        "decision_id": "other-candidate",
        "symbol": "MSFT",
        "decision_at": "2026-05-03T20:01:00Z",
    }[target]
    _write(bundle, manifest)

    assert _replay(bundle).signals == _signals()


@pytest.mark.parametrize("target", ["binding", "citation", "hash", "source"])
def test_unbound_or_mismatched_citations_are_neutral(bundle: Path, target: str) -> None:
    manifest = _read(bundle)
    output = _read(_output(bundle))
    if target == "binding":
        manifest["records"][0]["citation_bindings"] = []
    elif target == "citation":
        output["citations"] = []
    elif target == "hash":
        output["citations"][0]["raw_payload_hash"] = "0" * 64
    else:
        output["citations"][0]["source"] = "unbound source"
    _write(bundle, manifest)
    _write(_output(bundle), output)
    _repair(bundle)

    assert _replay(bundle).signals == _signals()


@pytest.mark.parametrize("direction", ["positive", "mixed", "neutral"])
def test_favorable_or_mixed_authority_never_reduces_or_adds_trades(
    bundle: Path, direction: str
) -> None:
    output = _read(_output(bundle))
    output["events"][0].update(direction=direction, blocking_risk=True, risk_level="blocking")
    output.update(hard_block=True, hard_block_reason="untrusted", size_multiplier=0.1)
    _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "no_adverse_events"


def test_raw_ai_size_and_score_have_no_authority_beyond_deterministic_adverse_policy(
    bundle: Path,
) -> None:
    output = _read(_output(bundle))
    output.update(size_multiplier=0.01, ai_score=90, hard_block=True, hard_block_reason="invented")
    _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert result.signals.decisions[0].quantity == 3
    assert result.diagnostics[0].ai_score < 50


def test_high_confidence_negative_block_cannot_revive_a_rejected_decision(bundle: Path) -> None:
    output = _read(_output(bundle))
    output["events"][0].update(blocking_risk=True, risk_level="blocking")
    _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert not result.signals.decisions[0].accepted
    assert result.signals.decisions[0].quantity == 0
    assert (
        result.signals.decisions[1].model_dump_json() == _signals().decisions[1].model_dump_json()
    )


def test_duplicate_articles_events_and_records_do_not_compound_size_or_score(bundle: Path) -> None:
    original = _replay(bundle)
    manifest = _read(bundle)
    article = dict(manifest["articles"][0], article_id="article-alias")
    manifest["articles"].append(article)
    record = manifest["records"][0]
    record["citation_bindings"].append(
        {"citation_id": "citation-alias", "article_id": "article-alias"}
    )
    output = _read(_output(bundle))
    output["citations"].append(dict(output["citations"][0], citation_id="citation-alias"))
    output["events"].append(
        dict(output["events"][0], event_id="event-alias", citation_ids=["citation-alias"])
    )
    manifest["records"].append(dict(record))
    _write(bundle, manifest)
    _write(_output(bundle), output)
    _repair(bundle)
    replay = _replay(bundle)

    assert replay.signals == original.signals
    assert replay.diagnostics[0].ai_score == original.diagnostics[0].ai_score
    assert replay.diagnostics[0].adverse_event_count == 1
    assert "duplicate_record" in replay.warnings


def test_latest_asof_output_wins_once_and_order_is_stable(bundle: Path) -> None:
    manifest = _read(bundle)
    older = dict(
        manifest["records"][0], record_id="older", output_available_at="2026-05-04T19:30:00Z"
    )
    manifest["records"].insert(0, older)
    _write(bundle, manifest)
    first = _replay(bundle)
    manifest["records"].reverse()
    _write(bundle, manifest)
    second = _replay(bundle)

    assert first.signals == second.signals
    assert first.diagnostics == second.diagnostics
    assert [d.decision_id for d in first.signals.decisions] == ["accepted-aapl", "rejected-aapl"]


@pytest.mark.parametrize("filename", ["article.json", "negative-output.json", "prompt.txt"])
def test_content_hash_mismatch_is_an_explicit_integrity_failure(
    bundle: Path, filename: str
) -> None:
    module = _module()
    with (bundle.parent / filename).open("ab") as stream:
        stream.write(b"tampering")

    with pytest.raises(module.FrozenAIIntegrityError, match="file_integrity_mismatch"):
        module.load_frozen_ai_evidence(bundle)


def test_invalid_manifest_and_escaping_local_paths_fail_explicitly(bundle: Path) -> None:
    module = _module()
    manifest = _read(bundle)
    manifest["records"][0]["output"]["path"] = "../outside.json"
    _write(bundle, manifest)
    with pytest.raises(module.FrozenAIIntegrityError, match="unsafe_local_path"):
        module.load_frozen_ai_evidence(bundle)
    bundle.write_text("{broken")
    with pytest.raises(module.FrozenAIIntegrityError, match="invalid_manifest"):
        module.load_frozen_ai_evidence(bundle)


def test_offline_import_and_replay_block_provider_and_broker_imports() -> None:
    script = """
import importlib.abc
import sys
from datetime import datetime, UTC
from pathlib import Path
class BlockOnline(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ("packages.ai.openai", "packages.ai.providers", "packages.execution", "apps.")
        if fullname.startswith(forbidden):
            raise AssertionError("online runtime import: " + fullname)
sys.meta_path.insert(0, BlockOnline())
from packages.research.ai_replay import load_frozen_ai_evidence, replay_ai_evidence
from packages.research.models import ResearchSignalSet
evidence = load_frozen_ai_evidence(Path("tests/fixtures/ai_replay/manifest.json"))
result = replay_ai_evidence(
    ResearchSignalSet(decisions=()), evidence, datetime(2026,5,4,20,1,tzinfo=UTC)
)
assert result.signals.decisions == ()
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_lazy_ai_package_preserves_legacy_public_exports() -> None:
    import packages.ai as ai

    assert (
        ai.parse_ai_trade_research_json
        is importlib.import_module("packages.ai.parser").parse_ai_trade_research_json
    )
    assert ai.FakeOpenAIClient is importlib.import_module("packages.ai.openai").FakeOpenAIClient


def test_output_cannot_use_an_article_observed_after_its_analysis(bundle: Path) -> None:
    manifest = _read(bundle)
    manifest["articles"][0]["observed_available_at"] = "2026-05-04T19:30:00Z"
    _write(bundle, manifest)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "article_not_available_at_analysis"


def test_output_cannot_describe_an_event_after_its_analysis(bundle: Path) -> None:
    output = _read(_output(bundle))
    output["events"][0]["published_at"] = "2026-05-04T19:30:00Z"
    _write(_output(bundle), output)
    _repair(bundle)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "event_after_analysis"


def test_bound_evidence_cannot_create_a_trade_from_a_rejected_shortlist(bundle: Path) -> None:
    manifest = _read(bundle)
    manifest["records"][0]["decision_id"] = "rejected-aapl"
    _write(bundle, manifest)
    rejected = ResearchSignalSet(decisions=(_signals().decisions[1],))
    module = _module()
    result = module.replay_ai_evidence(rejected, module.load_frozen_ai_evidence(bundle), CUTOFF)

    assert result.signals.model_dump_json() == rejected.model_dump_json()
    assert result.signals.accepted_signals == ()


def test_floor_reduction_to_zero_rejects_the_previously_accepted_trade(bundle: Path) -> None:
    signals = ResearchSignalSet(
        decisions=(_signals().decisions[0].model_copy(update={"quantity": 1}),)
    )
    module = _module()
    result = module.replay_ai_evidence(signals, module.load_frozen_ai_evidence(bundle), CUTOFF)

    assert result.signals.decisions[0].quantity == 0
    assert not result.signals.decisions[0].accepted


def test_future_global_cutoff_and_missing_article_neutral_fallback(bundle: Path) -> None:
    module = _module()
    evidence = module.load_frozen_ai_evidence(bundle)
    result = module.replay_ai_evidence(_signals(), evidence, CUTOFF - timedelta(seconds=1))
    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "decision_after_cutoff"
    (bundle.parent / "article.json").unlink()
    result = _replay(bundle)
    assert result.signals == _signals()
    assert result.diagnostics[0].reason == "missing_article"


def test_latest_malformed_output_never_selects_older_valid_output(bundle: Path) -> None:
    manifest = _read(bundle)
    newer = dict(manifest["records"][0], record_id="newer")
    newer["output_available_at"] = "2026-05-04T20:00:00Z"
    raw = b"{broken"
    (bundle.parent / "broken.json").write_bytes(raw)
    newer["output"] = {
        "path": "broken.json",
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    manifest["records"].append(newer)
    _write(bundle, manifest)
    result = _replay(bundle)

    assert result.signals == _signals()
    assert result.diagnostics[0].record_id == "newer"
    assert result.diagnostics[0].reason == "invalid_json"


def test_naive_cutoff_is_rejected_explicitly(bundle: Path) -> None:
    module = _module()

    with pytest.raises(ValueError, match="decision_cutoff_requires_offset"):
        module.replay_ai_evidence(
            _signals(), module.load_frozen_ai_evidence(bundle), datetime(2026, 5, 4)
        )


def test_research_fixture_replays_actual_baseline_ids_without_changing_warmup_or_rejections() -> (
    None
):
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.models import ResearchConfig
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_text())
    )
    original = generate_research_signals(snapshot, config)
    module = _module()
    evidence = module.load_frozen_ai_evidence(FIXTURE / "research" / "manifest.json")
    cutoff = snapshot.sessions[-1].decision_at
    neutral = module.replay_ai_evidence(original, evidence, cutoff, neutral_control=True)
    negative = module.replay_ai_evidence(original, evidence, cutoff)
    first_id = "8010b973262d56376bac824c10c3b91fb65c9ac6e2cb7af611d491a6ed4e6b07"
    second_id = "7a7a97705eac7520429fd314d1c0e86fc09bb3f23cd7d9250780025dc6c9aff8"
    source_by_id = {decision.decision_id: decision for decision in original.decisions}
    result_by_id = {decision.decision_id: decision for decision in negative.signals.decisions}

    assert len(original.decisions) == 630
    assert len(original.accepted_signals) == 10
    assert sum("insufficient_warmup" in d.reason_codes for d in original.decisions) == 597
    assert source_by_id[first_id].decision_session == date(2025, 10, 9)
    assert source_by_id[second_id].decision_session == date(2025, 10, 13)
    assert source_by_id[first_id].decision_at == snapshot.sessions[200].decision_at
    assert source_by_id[second_id].decision_at == snapshot.sessions[202].decision_at
    assert source_by_id[first_id].quantity == 1
    assert source_by_id[second_id].quantity == 2
    assert neutral.signals.model_dump_json() == original.model_dump_json()
    assert result_by_id[first_id].quantity == 0
    assert not result_by_id[first_id].accepted
    assert result_by_id[second_id].quantity == 1
    assert result_by_id[second_id].accepted
    assert len(negative.signals.accepted_signals) == 9
    assert [d.decision_id for d in negative.signals.decisions] == [
        d.decision_id for d in original.decisions
    ]
    for before, after in zip(original.decisions, negative.signals.decisions, strict=True):
        assert after.quantity <= before.quantity
        assert not after.accepted or before.accepted
        if before.decision_id not in {first_id, second_id}:
            assert after.model_dump_json() == before.model_dump_json()
        else:
            for field in (
                "decision_id",
                "symbol",
                "action",
                "decision_session",
                "decision_at",
                "eligible_session",
                "reference_price",
                "stop_price",
                "breakout_level",
            ):
                assert getattr(after, field) == getattr(before, field)
    applied = [row for row in negative.diagnostics if row.reason.startswith("adverse_")]
    assert [(row.decision_id, row.reason, row.size_multiplier) for row in applied] == [
        (first_id, "adverse_block", 0.0),
        (second_id, "adverse_reduction", 0.5),
    ]


def test_research_fixture_freezes_causal_synthetic_provenance_and_complete_baseline_settings() -> (
    None
):
    module = _module()
    path = FIXTURE / "research" / "manifest.json"
    evidence = module.load_frozen_ai_evidence(path)

    assert evidence.manifest is not None
    manifest = evidence.manifest
    assert manifest.kind == "synthetic"
    assert manifest.frozen_at <= datetime(2025, 12, 1, tzinfo=UTC)
    assert len(evidence.records) == len(evidence.articles) == 2
    for loaded_record, loaded_article in zip(evidence.records, evidence.articles, strict=True):
        assert loaded_article.article is not None
        record = loaded_record.metadata
        assert (
            loaded_article.article.published_at
            < loaded_article.metadata.observed_available_at
            < record.analysis_at
            < record.output_available_at
            < record.decision_at
        )
        assert record.decision_at.time().isoformat() == "20:01:00"
        assert record.output_available_at <= manifest.frozen_at
        output = json.loads(loaded_record.raw_output)
        assert all(event["direction"] == "negative" for event in output["events"])
        assert output["model_version"] == "hand-authored-research-illustration/v1"
    model_descriptor = _read(path.parent / manifest.model.file.path)
    settings = model_descriptor["effective_settings"]
    baseline_path = Path("experiments/configs/baseline.yaml")
    assert settings["baseline_config"] == json.loads(
        json.dumps(yaml.safe_load(baseline_path.read_text()), default=str)
    )
    assert (
        settings["baseline_config_sha256"] == hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    )
    assert settings["dataset_manifest_sha256"] == (
        "7057ce77e118a3adfebbda8aba85a317b3b74ba30bcd1ae2da055b1410f582ed"
    )
    assert settings["ai_policy"] == {
        "scoring_policy_version": "research-ai-negative-only/v1",
        "hard_block_confidence_min": 0.7,
        "comparison": ["AI_NEUTRAL", "AI_NEGATIVE_ONLY"],
        "neutral_control_changes_non_ai_settings": False,
    }


def test_resolved_evidence_fingerprint_distinguishes_missing_constituents_and_reproduces(
    bundle: Path, tmp_path: Path
) -> None:
    module = _module()
    complete = module.load_frozen_ai_evidence(bundle)
    output_bytes = _output(bundle).read_bytes()
    _output(bundle).unlink()
    missing_output = module.load_frozen_ai_evidence(bundle)
    output_repeat = module.load_frozen_ai_evidence(bundle)
    _output(bundle).write_bytes(output_bytes)
    (bundle.parent / "article.json").unlink()
    missing_article = module.load_frozen_ai_evidence(bundle)
    relocated = tmp_path / "relocated"
    shutil.copytree(bundle.parent, relocated)
    article_repeat = module.load_frozen_ai_evidence(relocated / "manifest.json")

    assert (
        complete.manifest_sha256
        == missing_output.manifest_sha256
        == missing_article.manifest_sha256
    )
    assert (
        len(
            {
                complete.resolved_sha256,
                missing_output.resolved_sha256,
                missing_article.resolved_sha256,
            }
        )
        == 3
    )
    assert missing_output.resolved_sha256 == output_repeat.resolved_sha256
    assert missing_article.resolved_sha256 == article_repeat.resolved_sha256
    assert any("missing_output" in warning for warning in missing_output.warnings)
    assert any("missing_article" in warning for warning in missing_article.warnings)
    for evidence, missing_path in (
        (missing_output, "negative-output.json"),
        (missing_article, "article.json"),
    ):
        resolution = next(row for row in evidence.file_resolutions if row.file.path == missing_path)
        assert resolution.status == "missing"
        assert resolution.verified_sha256 is None
        replayed = module.replay_ai_evidence(_signals(), evidence, CUTOFF)
        assert replayed.signals.model_dump_json() == _signals().model_dump_json()
    for resolution in complete.file_resolutions:
        assert resolution.status == "verified"
        assert resolution.verified_sha256 == resolution.file.sha256
        assert resolution.verified_size_bytes == resolution.file.size_bytes


def test_resolved_evidence_changes_root_case_identity_and_published_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.research import runner

    module = _module()
    root = tmp_path / "evidence"
    shutil.copytree(FIXTURE / "research", root)
    manifest_path = root / "manifest.json"
    registration = yaml.safe_load(Path("experiments/configs/ablations.yaml").read_bytes())
    registration["baseline_config"] = str(Path("experiments/configs/baseline.yaml").absolute())
    registration["matrix"]["ai_manifest"] = str(manifest_path)
    # Keep the real causal generator/simulation path with both affected candidates,
    # without repeating unrelated matrix axes.
    registration["matrix"]["ablations"] = registration["matrix"]["ablations"][:1]
    registration["matrix"]["costs"] = registration["matrix"]["costs"][:1]
    config_path = tmp_path / "matrix.yaml"
    config_path.write_text(yaml.safe_dump(registration))
    captures: list[dict[str, bytes]] = []

    def capture(_output: Path, files: dict[str, bytes], _runtime: bytes) -> None:
        captures.append(files)

    # Hold source provenance fixed to isolate evidence resolution from concurrent
    # source development; capture publication at the real writer boundary.
    monkeypatch.setattr(runner, "_source_identity", lambda: {"sha256": "fixed-test-source"})
    monkeypatch.setattr(runner, "publish_artifacts", capture)

    def evaluate(label: str) -> tuple[Any, dict[str, bytes]]:
        summary = runner.evaluate_research(
            config_path, Path("tests/fixtures/market_snapshot/manifest.json"), tmp_path / label
        )
        return summary, captures[-1]

    complete, complete_files = evaluate("complete")
    raw_output = (root / "output-200.json").read_bytes()
    (root / "output-200.json").unlink()
    output_missing, output_files = evaluate("missing-output")
    output_repeat, output_repeat_files = evaluate("missing-output-repeat")
    output_evidence = module.load_frozen_ai_evidence(manifest_path)
    (root / "output-200.json").write_bytes(raw_output)
    (root / "article-200.json").unlink()
    article_missing, article_files = evaluate("missing-article")
    article_repeat, article_repeat_files = evaluate("missing-article-repeat")
    article_evidence = module.load_frozen_ai_evidence(manifest_path)

    assert len({complete.run_id, output_missing.run_id, article_missing.run_id}) == 3
    assert output_missing.run_id == output_repeat.run_id
    assert output_missing.deterministic_sha256 == output_repeat.deterministic_sha256
    assert output_files == output_repeat_files
    assert article_missing.run_id == article_repeat.run_id
    assert article_missing.deterministic_sha256 == article_repeat.deterministic_sha256
    assert article_files == article_repeat_files
    case_sets = [
        {row["case_id"] for row in json.loads(files["matrix.json"])["cases"]}
        for files in (complete_files, output_files, article_files)
    ]
    assert case_sets[0].isdisjoint(case_sets[1])
    assert case_sets[0].isdisjoint(case_sets[2])
    assert case_sets[1].isdisjoint(case_sets[2])
    for files, fingerprint, missing_path in (
        (output_files, output_evidence.resolved_sha256, "output-200.json"),
        (article_files, article_evidence.resolved_sha256, "article-200.json"),
    ):
        parent = json.loads(files["manifest.json"])
        matrix = json.loads(files["matrix.json"])
        assert parent["ai_resolved_evidence_sha256"] == fingerprint
        assert matrix["resolved_evidence_sha256"] == fingerprint
        missing = next(
            row for row in parent["ai_evidence_resolution"] if row["file"]["path"] == missing_path
        )
        assert missing["status"] == "missing"
        assert missing["verified_sha256"] is None
        assert any(missing_path in warning for warning in matrix["warnings"])
        for case in matrix["cases"]:
            manifest = json.loads(files[case["artifact_path"] + "/manifest.json"])
            assert manifest["ai_resolved_evidence_sha256"] == fingerprint
            assert manifest["ai_evidence_resolution"] == parent["ai_evidence_resolution"]
