"""Aggregate budgets continue invented closed evidence without resetting quotas."""

from __future__ import annotations

import hashlib
import importlib
import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

from packages.data.acquisition_budget import BudgetedHistoricalTransport
from packages.data.alpaca_historical import BARS_ENDPOINT, HistoricalAcquisitionError, HttpResponse


def api() -> Any:
    return importlib.import_module("packages.data.checkpoint_budget")


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def seed_events() -> list[dict[str, object]]:
    rows = []
    total = 0
    for attempt, count in ((1, 924), (2, 533)):
        common = {
            "attempt_id": attempt,
            "attempts": attempt,
            "max_attempts": 100,
            "max_received_body_bytes": 262144000,
            "max_elapsed_seconds": 900,
            "min_interval_seconds": 0.35,
            "elapsed_seconds": float(attempt),
        }
        rows.append(
            common
            | {
                "event": "attempt_reserved",
                "received_body_bytes": total,
                "successful_body_bytes": total,
                "request_body_budget": 16777216,
                "endpoint_path": "/v2/stocks/bars",
                "query_sha256": "a" * 64,
            }
        )
        total += count
        rows.append(
            common
            | {
                "event": "body_received",
                "chunk_bytes": count,
                "received_body_bytes": total,
                "successful_body_bytes": total,
                "status_code": 200,
            }
        )
        rows.append(
            common
            | {
                "event": "attempt_finished",
                "received_body_bytes": total,
                "successful_body_bytes": total,
                "status_code": 200,
                "error_code": None,
            }
        )
    return rows


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    (repository / ".gitignore").write_text("/datasets/**\n")
    base = repository / "datasets/private/r4b"
    seed = base / "original/runtime/budget.jsonl"
    seed.parent.mkdir(parents=True)
    seed.write_bytes(b"".join(map(encoded, seed_events())))
    return (
        repository,
        base / "checkpoint-authority",
        seed,
        hashlib.sha256(seed.read_bytes()).hexdigest(),
    )


def authority(layout: tuple[Path, Path, Path, str], **changes: Any) -> Any:
    repository, directory, seed, digest = layout
    return api().CheckpointBudgetAuthority(
        directory, repository, seed, changes.pop("expected_seed_sha256", digest), **changes
    )


class Clock:
    value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class Transport:
    def __init__(self, body: bytes = b"abc", *, interrupt: bool = False) -> None:
        self.body, self.interrupt, self.calls = body, interrupt, 0

    def get_bounded(
        self, endpoint: str, params: object, timeout: float, **callbacks: Any
    ) -> HttpResponse:
        callbacks["request_started"]()
        self.calls += 1
        if self.interrupt:
            raise KeyboardInterrupt
        callbacks["response_started"](200)
        assert len(self.body) <= callbacks["max_body_bytes"]
        callbacks["body_received"](len(self.body))
        return HttpResponse(200, {}, self.body)


def get_once(guard: Any, transport: Transport | None = None) -> Any:
    clock = Clock()
    budget = guard.session_budget(monotonic=clock, sleep=clock.sleep)
    BudgetedHistoricalTransport(transport=transport or Transport(), budget=budget).get(
        BARS_ENDPOINT, {"feed": "iex"}, 10
    )
    return budget


def test_closed_original_seed_is_read_only_and_new_session_starts_with_prior_totals(layout) -> None:
    before = layout[2].read_bytes()
    with authority(layout) as guard:
        budget = get_once(guard)
        assert budget.attempts == 3
        assert budget.received_body_bytes == budget.successful_body_bytes == 1460
    assert layout[2].read_bytes() == before
    for path in (layout[1], *layout[1].rglob("*")):
        assert stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)


def test_later_session_continues_prior_authority_totals_without_refunding(layout) -> None:
    with authority(layout) as guard:
        get_once(guard)
    with authority(layout) as guard:
        budget = get_once(guard, Transport(b"12345"))
        assert budget.attempts == 4 and budget.received_body_bytes == 1465


def test_prior_requests_count_toward_hard_hundred_attempt_ceiling(layout) -> None:
    with authority(layout) as guard:
        clock, transport = Clock(), Transport(b"x")
        budget = guard.session_budget(monotonic=clock, sleep=clock.sleep)
        bounded = BudgetedHistoricalTransport(transport=transport, budget=budget)
        for _ in range(98):
            bounded.get(BARS_ENDPOINT, {}, 10)
        with pytest.raises(HistoricalAcquisitionError, match="session_attempt_limit"):
            bounded.get(BARS_ENDPOINT, {}, 10)
        assert budget.attempts == 100 and transport.calls == 98


def test_prior_bytes_count_toward_hard_global_body_ceiling(layout) -> None:
    with authority(layout) as guard:
        clock, transport = Clock(), Transport()
        budget = guard.session_budget(monotonic=clock, sleep=clock.sleep)
        bounded = BudgetedHistoricalTransport(transport=transport, budget=budget)
        remaining = 262144000 - 1457
        while remaining:
            size = min(16777216, remaining)
            transport.body = b"x" * size
            bounded.get(BARS_ENDPOINT, {}, 10)
            remaining -= size
        with pytest.raises(HistoricalAcquisitionError, match="session_byte_limit"):
            bounded.get(BARS_ENDPOINT, {}, 10)
        assert budget.received_body_bytes == 262144000
        assert transport.calls == 16


def test_inflight_attempt_blocks_new_session_after_interruption(layout) -> None:
    with pytest.raises(KeyboardInterrupt), authority(layout) as guard:
        get_once(guard, Transport(interrupt=True))
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_inflight"):
        with authority(layout):
            pytest.fail("interrupted checkpoint was automatically resumed")


def test_wrong_seed_hash_creates_no_authority_and_preserves_original(layout) -> None:
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_seed"):
        with authority(layout, expected_seed_sha256="0" * 64):
            pytest.fail("wrong seed was accepted")
    assert not layout[1].exists()


@pytest.mark.parametrize("mutation", ["inflight", "wrong_total", "truncated"])
def test_invalid_original_seed_never_initializes_fresh_quota(layout, mutation: str) -> None:
    rows = seed_events()
    if mutation == "inflight":
        rows.pop()
    elif mutation == "wrong_total":
        rows[-1]["received_body_bytes"] = 0
    raw = b"".join(map(encoded, rows))
    if mutation == "truncated":
        raw = raw[:-1]
    layout[2].write_bytes(raw)
    changed = (*layout[:3], hashlib.sha256(raw).hexdigest())
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_seed"):
        with authority(changed):
            pytest.fail("invalid seed reset a checkpoint")
    assert not layout[1].exists()


def test_seed_changed_after_initialization_is_not_accepted(layout) -> None:
    with authority(layout):
        pass
    layout[2].write_bytes(layout[2].read_bytes() + b"\n")
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_seed"):
        with authority(layout):
            pytest.fail("changed prior evidence was accepted")


@pytest.mark.parametrize("mutation", ["change", "truncate_line", "remove_valid_tail", "missing"])
def test_journal_corruption_or_truncation_cannot_restore_consumed_quota(
    layout, mutation: str
) -> None:
    with authority(layout) as guard:
        get_once(guard)
    journal = layout[1] / "events.jsonl"
    raw = journal.read_bytes()
    if mutation == "change":
        journal.write_bytes(raw.replace(b'"attempts":3', b'"attempts":2', 1))
    elif mutation == "truncate_line":
        journal.write_bytes(raw[:-1])
    elif mutation == "remove_valid_tail":
        journal.write_bytes(b"\n".join(raw.splitlines()[:-1]) + b"\n")
    else:
        journal.unlink()
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_journal"):
        with authority(layout):
            pytest.fail("damaged journal was reset")


def test_one_host_lock_rejects_overlapping_authorities(layout) -> None:
    with authority(layout):
        with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_busy"):
            with authority(layout):
                pytest.fail("overlapping checkpoint owner")


def test_nested_same_authority_object_does_not_lose_its_existing_lock(layout) -> None:
    guard = authority(layout)
    with guard:
        with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_busy"):
            with guard:
                pytest.fail("nested same-object lock")
        get_once(guard)
    with authority(layout) as later:
        assert later.snapshot()["attempts"] == 3


def test_another_fresh_authority_directory_cannot_reset_the_checkpoint(layout) -> None:
    with authority(layout) as guard:
        get_once(guard)
    alternative = (layout[0], layout[1].with_name("different-authority"), layout[2], layout[3])
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_journal"):
        with authority(alternative):
            pytest.fail("different directory reset aggregate consumption")


def test_deleted_authority_state_cannot_be_automatically_reinitialized(layout) -> None:
    with authority(layout) as guard:
        get_once(guard)
    import shutil

    shutil.rmtree(layout[1])
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_journal"):
        with authority(layout):
            pytest.fail("missing authority was automatically replaced")


def test_global_storage_counts_prior_sibling_workspaces_and_new_journal_files(layout) -> None:
    prior = layout[0] / "datasets/private/r4b/issuer-evidence"
    prior.mkdir()
    (prior / "original-workbook").write_bytes(b"x" * 123)
    with authority(layout) as guard:
        actual = sum(p.stat().st_size for p in prior.parent.rglob("*") if p.is_file())
        guard.check_storage(additional_bytes=1024**3 - actual)
        with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_storage_limit"):
            guard.check_storage(additional_bytes=1024**3 - actual + 1)


def test_global_storage_refuses_symlinked_evidence(layout, tmp_path: Path) -> None:
    with authority(layout) as guard:
        (layout[0] / "datasets/private/r4b/link").symlink_to(tmp_path / "outside")
        with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_path"):
            guard.check_storage()


def test_storage_guard_cannot_authorize_writes_after_exclusive_context_closes(layout) -> None:
    with authority(layout) as guard:
        pass
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_journal"):
        guard.check_storage(1)


def test_second_budget_in_same_context_is_rejected_instead_of_reusing_initial_totals(
    layout,
) -> None:
    with authority(layout) as guard:
        get_once(guard)
        with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_session_exists"):
            guard.session_budget()


def test_optional_previous_receipt_is_verified_before_authority_creation(layout) -> None:
    receipt = layout[2].parent / "receipt.json"
    receipt.write_bytes(b"invented receipt")
    reference = api().BudgetReceiptReference(receipt, "0" * 64, len(receipt.read_bytes()))
    with pytest.raises(api().CheckpointBudgetError, match="checkpoint_budget_seed"):
        with authority(layout, prior_receipts=(reference,)):
            pytest.fail("invalid receipt accepted")
    assert not layout[1].exists()
