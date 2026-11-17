"""Finite end-to-end acquisition uses original synthetic HTTP responses only."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.data.alpaca_historical import HttpResponse
from packages.data.historical_candidates import load_historical_candidate


def api():
    try:
        return importlib.import_module("packages.data.acquisition_session")
    except ModuleNotFoundError:
        pytest.fail("acquisition session implementation missing")


class SyntheticTransport:
    def __init__(
        self,
        registered,
        *,
        forbidden=False,
        missing_pilot=False,
        malformed=False,
        unsupported_pilot_action=False,
        special_preflight=False,
    ):
        self.registered = registered
        self.forbidden = forbidden
        self.missing_pilot = missing_pilot
        self.malformed = malformed
        self.unsupported_pilot_action = unsupported_pilot_action
        self.special_preflight = special_preflight
        self.calls = []

    def get_bounded(self, endpoint, params, timeout_seconds, **callbacks):
        callbacks["request_started"]()
        self.calls.append((endpoint, dict(params)))
        status = 403 if self.forbidden else 200
        if self.malformed:
            body = b'{"bars":false}'
        elif "corporate-actions" in endpoint:
            if self.special_preflight and params["end"] == "2024-03-31":
                body = json.dumps(
                    {
                        "corporate_actions": {
                            "cash_dividends": [
                                {
                                    "symbol": "SPY",
                                    "id": "synthetic-special",
                                    "foreign": False,
                                    "special": True,
                                    "rate": 1,
                                    "ex_date": "2024-03-01",
                                    "payable_date": "2024-03-15",
                                    "process_date": "2024-03-01",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                ).encode()
                callbacks["response_started"](status)
                callbacks["body_received"](len(body))
                return HttpResponse(status, {}, body)
            body = (
                b'{"corporate_actions":{"mergers":[{"symbol":"QQQ"}]},"next_page_token":null}'
                if self.unsupported_pilot_action
                and params["start"] == "2024-01-01"
                and params["end"] == "2026-11-16"
                else b'{"corporate_actions":{},"next_page_token":null}'
            )
        else:
            start, end = params["start"][:10], params["end"][:10]
            rows = {}
            for symbol in params["symbols"].split(","):
                sessions = [
                    s for s in self.registered.calendar.sessions if start <= str(s.date) <= end
                ]
                if self.missing_pilot and start == "2024-01-01":
                    sessions = sessions[1:]
                rows[symbol] = [
                    {
                        "t": f"{s.date}T05:00:00Z"
                        if s.open_at.hour == 14
                        else f"{s.date}T04:00:00Z",
                        "o": 10,
                        "h": 12,
                        "l": 9,
                        "c": 11,
                        "v": 100,
                    }
                    for s in sessions
                ]
            body = json.dumps({"bars": rows, "next_page_token": None}).encode()
        callbacks["response_started"](status)
        callbacks["body_received"](len(body))
        return HttpResponse(status, {}, body)


class Clock:
    seconds = 0.0

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds

    def utc(self):
        return datetime(2026, 11, 17, 12, tzinfo=UTC)


def setup(tmp_path):
    from packages.data.acquisition_plan import load_acquisition_plan

    registered = load_acquisition_plan(Path("experiments/configs/r4b_acquisition.json"))
    repo = tmp_path / "repository"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("datasets/private/\n")
    return registered, repo, repo / "datasets/private/r4b/test"


def run(tmp_path, **options):
    module = api()
    registered, repo, workspace = setup(tmp_path)
    transport = SyntheticTransport(registered, **options)
    clock = Clock()
    result = module.acquire_registered_candidate(
        registered,
        repository=repo,
        workspace=workspace,
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    return result, transport, workspace


def test_complete_synthetic_session_freezes_verified_private_candidate(tmp_path):
    result, transport, workspace = run(tmp_path)
    candidate = load_historical_candidate(result.manifest_path)
    assert candidate.manifest.kind == "synthetic"
    assert len(candidate.manifest.acquisitions) == 21
    assert result.pilot_passed
    assert result.attempts == len(transport.calls) == 21
    assert result.received_body_bytes > 0
    assert result.manifest_path.is_relative_to(workspace)
    assert all(request.get("feed", "iex") == "iex" for _, request in transport.calls)
    assert all(path.stat().st_mode & 0o077 == 0 for path in workspace.rglob("*") if path.is_file())
    assert (workspace / "registered-plan.json").is_file()
    assert (workspace / "runtime/budget.jsonl").is_file()
    assert candidate.manifest.availability.mode == "synthetic"


@pytest.mark.parametrize(
    "option,error", [("forbidden", "forbidden"), ("malformed", "invalid_page")]
)
def test_preflight_failure_stops_network_and_preserves_evidence(tmp_path, option, error):
    result, transport, _ = run(tmp_path, **{option: True})
    assert result.attempts == len(transport.calls) == 1
    assert not result.pilot_passed
    candidate = load_historical_candidate(result.manifest_path)
    assert candidate.manifest.acquisitions[0].error_code == error
    assert not candidate.manifest.acquisitions[0].complete


def test_missing_pilot_blocks_larger_primary_acquisition(tmp_path):
    result, transport, _ = run(tmp_path, missing_pilot=True)
    candidate = load_historical_candidate(result.manifest_path)
    assert not result.pilot_passed
    assert not any(a.role == "candidate" for a in candidate.manifest.acquisitions)
    assert len(transport.calls) < 21


def test_unsupported_pilot_action_blocks_larger_primary_acquisition(tmp_path):
    result, _, _ = run(tmp_path, unsupported_pilot_action=True)
    candidate = load_historical_candidate(result.manifest_path)
    assert not result.pilot_passed
    assert not any(a.role == "candidate" for a in candidate.manifest.acquisitions)


def test_http_error_evidence_is_retained_privately(tmp_path):
    result, _, _ = run(tmp_path, forbidden=True)
    candidate = load_historical_candidate(result.manifest_path)
    page = candidate.manifest.acquisitions[0].pages[0]
    assert page.http_status == 403
    assert candidate.files[page.file_path]
    assert candidate.acquisitions[0].pages == ()


def test_synthetic_special_preflight_stops_after_two_requests(tmp_path):
    result, transport, _ = run(tmp_path, special_preflight=True)
    assert result.attempts == len(transport.calls) == 2
    assert result.stopped_code == "unsupported_corporate_action"
    candidate = load_historical_candidate(result.manifest_path)
    assert candidate.manifest.acquisitions[1].complete
    assert candidate.manifest.acquisitions[1].normalization_error_code == (
        "unsupported_corporate_action"
    )
    assert not any(a.role in {"pilot", "candidate"} for a in candidate.manifest.acquisitions)


def test_offline_qualification_repeats_identical_bytes_and_rejects_overwrite(tmp_path):
    result, _, workspace = run(tmp_path)
    first = api().qualify_candidate(result.manifest_path, workspace / "check-one")
    second = api().qualify_candidate(result.manifest_path, workspace / "check-two")
    assert first["hashes"] == second["hashes"]
    assert (workspace / "check-one/qualification.json").read_bytes() == (
        workspace / "check-two/qualification.json"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        api().qualify_candidate(result.manifest_path, workspace / "check-one")


def test_cli_cannot_access_credentials_or_network_without_explicit_opt_in(tmp_path):
    try:
        cli = importlib.import_module("packages.data.acquisition_cli")
    except ModuleNotFoundError:
        pytest.fail("acquisition CLI implementation missing")
    with patch("packages.data.acquisition_cli.load_alpaca_credentials") as secret:
        assert (
            cli.main(
                [
                    "acquire",
                    "--plan",
                    "experiments/configs/r4b_acquisition.json",
                    "--workspace",
                    str(tmp_path / "private"),
                    "--credentials-file",
                    str(tmp_path / "secret"),
                ]
            )
            == 2
        )
    secret.assert_not_called()


def test_historical_qualification_cannot_publish_outside_private_workspace(tmp_path):
    result, _, workspace = run(tmp_path)
    # Preserve a truthful separate immutable historical envelope for the path gate test.
    payload = json.loads(result.manifest_path.read_bytes())
    payload["kind"] = "historical"
    payload["availability"]["mode"] = "observed"
    result.manifest_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="private_qualification_output_required"):
        api().qualify_candidate(result.manifest_path, workspace / "../../../../public-result")
    with pytest.raises(ValueError, match="private_qualification_output_required"):
        api().qualify_candidate(result.manifest_path, workspace / "../other-private-result")


def test_actual_cli_plan_and_qualification_are_offline(tmp_path, capsys):
    cli = importlib.import_module("packages.data.acquisition_cli")
    with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network")):
        assert cli.main(["plan", "--plan", "experiments/configs/r4b_acquisition.json"]) == 0
        result, _, workspace = run(tmp_path)
        assert (
            cli.main(
                [
                    "qualify",
                    "--candidate",
                    str(result.manifest_path),
                    "--output",
                    str(workspace / "cli-check"),
                ]
            )
            == 0
        )
    assert '"network": false' in capsys.readouterr().out


def test_partial_acquisition_cli_returns_failure_without_private_exception_text(tmp_path, capsys):
    from packages.data.acquisition_plan import AlpacaCredentials
    from packages.data.acquisition_session import AcquisitionResult

    cli = importlib.import_module("packages.data.acquisition_cli")
    with (
        patch.object(
            cli, "load_alpaca_credentials", return_value=AlpacaCredentials("fake", "fake")
        ),
        patch.object(cli, "UrllibHistoricalTransport"),
        patch.object(
            cli,
            "acquire_registered_candidate",
            return_value=AcquisitionResult(
                tmp_path / "manifest.json", 2, 100, 100, False, "unsupported_corporate_action"
            ),
        ),
    ):
        code = cli.main(
            [
                "acquire",
                "--allow-network",
                "--plan",
                "experiments/configs/r4b_acquisition.json",
                "--workspace",
                str(tmp_path),
                "--credentials-file",
                str(tmp_path / "fake"),
            ],
            repository=tmp_path,
        )
    assert code == 1
    output = capsys.readouterr().out
    assert "unsupported_corporate_action" in output and '"fake"' not in output


def test_reused_preflights_keep_original_times_and_make_no_new_gets(tmp_path):
    from packages.data.acquisition_plan import load_acquisition_plan

    result, _, workspace = run(tmp_path)
    original = load_historical_candidate(result.manifest_path)
    registered = load_acquisition_plan(Path("experiments/configs/r4b_acquisition.json"))
    transport = SyntheticTransport(registered)
    clock = Clock()
    second = api().acquire_registered_candidate(
        registered,
        repository=workspace.parents[3],
        workspace=workspace.parent / "reuse",
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        reused_acquisitions=dict(
            zip(("preflight-bars", "preflight-actions"), original.acquisitions[:2], strict=True)
        ),
        supplemental_evidence={"parent.json": b'{"synthetic":true}\n'},
    )
    candidate = load_historical_candidate(second.manifest_path)
    assert len(transport.calls) == 19
    assert candidate.acquisitions[:2] == original.acquisitions[:2]
    assert "evidence/supplemental/parent.json" in candidate.files


def test_external_pilot_gate_prevents_larger_queries(tmp_path):
    module = api()
    registered, repo, workspace = setup(tmp_path)
    transport = SyntheticTransport(registered)
    clock = Clock()
    result = module.acquire_registered_candidate(
        registered,
        repository=repo,
        workspace=workspace,
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        pilot_gate=lambda records, files: False,
    )
    candidate = load_historical_candidate(result.manifest_path)
    assert not result.pilot_passed
    assert not any(a.role == "candidate" for a in candidate.manifest.acquisitions)


def test_external_budget_starts_with_prior_consumption_and_global_storage_guard(tmp_path):
    from packages.data.acquisition_budget import HistoricalSessionBudget

    module = api()
    registered, repo, workspace = setup(tmp_path)
    transport, clock = SyntheticTransport(registered), Clock()
    checked = []
    result = module.acquire_registered_candidate(
        registered,
        repository=repo,
        workspace=workspace,
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        budget_factory=lambda storage: HistoricalSessionBudget(
            initial_attempts=2,
            initial_received_body_bytes=1457,
            initial_successful_body_bytes=1457,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            event_callback=storage.append_event,
        ),
        storage_guard=checked.append,
    )
    assert result.attempts == len(transport.calls) + 2
    assert result.received_body_bytes > 1457
    assert len(checked) > 25 and all(n >= 0 for n in checked)


@pytest.mark.parametrize(
    "hook,code", [("action_evaluator", "action_policy_failed"), ("pilot_gate", "pilot_gate_failed")]
)
def test_callback_failure_is_terminal_private_evidence(tmp_path, hook, code):
    registered, repo, workspace = setup(tmp_path)
    transport, clock = SyntheticTransport(registered), Clock()

    def failed(*args):
        raise ValueError("PRIVATE callback content")

    result = api().acquire_registered_candidate(
        registered,
        repository=repo,
        workspace=workspace,
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        **{hook: failed},
    )
    assert result.stopped_code == code
    candidate = load_historical_candidate(result.manifest_path)
    assert not any(a.role == "candidate" for a in candidate.manifest.acquisitions)
    assert all(b"PRIVATE callback" not in body for body in candidate.files.values())


def test_legacy_default_cannot_bypass_existing_checkpoint_authority(tmp_path):
    from packages.data.alpaca_historical import HistoricalAcquisitionError

    registered, repo, workspace = setup(tmp_path)
    workspace.parent.mkdir(parents=True)
    (workspace.parent / ".checkpoint-budget-authority.json").write_text("{}")
    transport = SyntheticTransport(registered)
    with pytest.raises(HistoricalAcquisitionError, match="checkpoint_authority_required"):
        api().acquire_registered_candidate(
            registered,
            repository=repo,
            workspace=workspace,
            transport=transport,
            kind="synthetic",
        )
    assert not transport.calls


def test_optional_pilot_failure_stop_retains_terminal_reason(tmp_path):
    from packages.data.acquisition_session import ActionEvaluation

    registered, repo, workspace = setup(tmp_path)
    transport, clock = SyntheticTransport(registered), Clock()
    result = api().acquire_registered_candidate(
        registered,
        repository=repo,
        workspace=workspace,
        transport=transport,
        kind="synthetic",
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        action_evaluator=lambda stage, acquisition, ids: ActionEvaluation(
            (), {}, "invalid_corporate_action" if stage.role == "pilot" else None
        ),
        stop_on_pilot_failure=True,
    )
    assert result.stopped_code == "invalid_corporate_action"
    assert len(transport.calls) == 4
    candidate = load_historical_candidate(result.manifest_path)
    assert len(candidate.manifest.acquisitions) == 4
    assert "normalized/pilot-actions-actions.json" not in candidate.files


def test_legacy_cli_checks_authority_before_secret_loading(tmp_path):
    cli = importlib.import_module("packages.data.acquisition_cli")
    private = tmp_path / "datasets/private/r4b"
    private.mkdir(parents=True)
    (private / ".checkpoint-budget-authority.json").write_text("{}")
    with patch.object(cli, "load_alpaca_credentials") as credentials:
        assert (
            cli.main(
                [
                    "acquire",
                    "--allow-network",
                    "--plan",
                    "experiments/configs/r4b_acquisition.json",
                    "--workspace",
                    str(private / "new"),
                    "--credentials-file",
                    str(tmp_path / "private.env"),
                ],
                repository=tmp_path,
            )
            == 1
        )
    credentials.assert_not_called()


def test_legacy_historical_publication_cannot_bypass_global_authority(tmp_path):
    from packages.data.private_storage import PrivateStorage, PrivateStorageError

    result, _, workspace = run(tmp_path)
    payload = json.loads(result.manifest_path.read_bytes())
    payload["kind"] = "historical"
    payload["availability"]["mode"] = "observed"
    result.manifest_path.write_text(json.dumps(payload))
    (workspace.parent / ".checkpoint-budget-authority.json").write_text("{}")
    with pytest.raises(PrivateStorageError, match="private_storage_authority_required"):
        PrivateStorage(workspace.parent / "bypass", workspace.parents[3])
    with pytest.raises(ValueError, match="checkpoint_authority_required"):
        api().qualify_candidate(result.manifest_path, workspace / "bypass-qualification")
