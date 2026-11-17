"""Explicit authorization, resource and secret-file parsing tests use fake values only."""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import pytest

PLAN = Path("experiments/configs/r4b_acquisition.json")
CALENDAR = Path("experiments/configs/r4b_calendar_2020_2025.json")


def _module():
    try:
        return importlib.import_module("packages.data.acquisition_plan")
    except ModuleNotFoundError:
        pytest.fail("registered acquisition plan implementation missing")


def _copy(tmp_path: Path, update=None) -> Path:
    payload = json.loads(PLAN.read_bytes())
    if update:
        update(payload)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(payload))
    shutil.copyfile(CALENDAR, tmp_path / CALENDAR.name)
    return path


def test_registered_plan_is_explicit_iex_and_finite() -> None:
    registered = _module().load_acquisition_plan(PLAN)
    assert registered.plan.feed == "iex"
    assert registered.plan.account_plan == "Basic"
    assert len(registered.plan.stages) == 21
    assert registered.plan.budget.max_attempts == 100
    assert registered.plan.budget.max_received_body_bytes == 262144000
    assert registered.plan.budget.max_local_bytes == 1073741824
    assert len(registered.calendar.sessions) == 1508


@pytest.mark.parametrize(
    "field,value",
    [
        ("feed", "sip"),
        ("account_plan", "Algo Trader Plus"),
        ("provider", "other"),
        ("account_type", "live"),
    ],
)
def test_entitlement_and_no_cost_scope_fail_closed(tmp_path: Path, field: str, value: str) -> None:
    path = _copy(tmp_path, lambda data: data.update({field: value}))
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_attempts", 101),
        ("max_received_body_bytes", 262144001),
        ("max_local_bytes", 1073741825),
        ("max_elapsed_seconds", 901),
        ("min_interval_seconds", 0),
        ("timeout_seconds", 121),
    ],
)
def test_plan_cannot_expand_checkpoint_budget(tmp_path: Path, field: str, value: int) -> None:
    path = _copy(tmp_path, lambda data: data["budget"].update({field: value}))
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


def test_plan_rejects_sip_hidden_in_one_request(tmp_path: Path) -> None:
    path = _copy(tmp_path, lambda data: data["stages"][0]["request"].update(feed="sip"))
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


def test_plan_rejects_adjusted_primary_execution(tmp_path: Path) -> None:
    path = _copy(tmp_path, lambda data: data["stages"][2]["request"].update(adjustment="all"))
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


def test_calendar_hash_and_relative_path_are_pinned(tmp_path: Path) -> None:
    path = _copy(tmp_path, lambda data: data.update(calendar_sha256="0" * 64))
    with pytest.raises(ValueError):
        _module().load_acquisition_plan(path)
    payload = json.loads(path.read_bytes())
    payload["calendar_path"] = "../private.env"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


def test_plan_requires_preflight_before_pilot_before_candidate(tmp_path: Path) -> None:
    path = _copy(tmp_path, lambda data: data["stages"].reverse())
    with pytest.raises(ValueError, match="invalid_acquisition_plan"):
        _module().load_acquisition_plan(path)


def test_secret_configuration_is_loaded_without_execution_or_mutation(tmp_path: Path) -> None:
    credentials = tmp_path / "test.env"
    credentials.write_text(
        '# Original fake test credentials\nexport APCA_API_KEY_ID="fake-test-key"\n'
        "APCA_API_SECRET_KEY='fake-test-secret'\n"
    )
    credentials.chmod(0o600)
    before, mode = credentials.read_bytes(), credentials.stat().st_mode
    result = _module().load_alpaca_credentials(credentials)
    assert result.api_key == "fake-test-key"
    assert result.secret_key == "fake-test-secret"
    assert "fake-test" not in repr(result)
    assert credentials.read_bytes() == before and credentials.stat().st_mode == mode


@pytest.mark.parametrize(
    "payload",
    [
        "APCA_API_KEY_ID=fake\n",
        "APCA_API_KEY_ID=fake\nAPCA_API_KEY_ID=other\nAPCA_API_SECRET_KEY=secret\n",
        "APCA_API_KEY_ID=fake\nAPCA_API_SECRET_KEY=secret\nUNKNOWN=value\n",
        "APCA_API_KEY_ID=fake\nAPCA_API_SECRET_KEY='broken\n",
        "APCA_API_KEY_ID=fake\nAPCA_API_SECRET_KEY=\n",
    ],
)
def test_invalid_credentials_fail_with_no_values_in_error(tmp_path: Path, payload: str) -> None:
    credentials = tmp_path / "test.env"
    credentials.write_text(payload)
    with pytest.raises(ValueError) as raised:
        _module().load_alpaca_credentials(credentials)
    assert str(raised.value) == "credentials_unavailable"
    assert "fake" not in str(raised.value) and "secret" not in str(raised.value)


@pytest.mark.parametrize(
    "payload",
    [
        "APCA_API_KEY_ID=$(touch SENTINEL)\nAPCA_API_SECRET_KEY=fake\n",
        "APCA_API_KEY_ID=`touch SENTINEL`\nAPCA_API_SECRET_KEY=fake\n",
        "APCA_API_KEY_ID=${UNRELATED}\nAPCA_API_SECRET_KEY=fake\n",
        "APCA_API_KEY_ID=fake;touch SENTINEL\nAPCA_API_SECRET_KEY=fake\n",
        'APCA_API_KEY_ID="fake\\nkey"\nAPCA_API_SECRET_KEY=fake\n',
        'APCA_API_KEY_ID="fake" trailing\nAPCA_API_SECRET_KEY=fake\n',
        "APCA_API_KEY_ID=" + "x" * 17000 + "\nAPCA_API_SECRET_KEY=fake\n",
    ],
)
def test_unsupported_shell_syntax_and_oversized_fake_files_are_never_executed(
    tmp_path: Path,
    payload: str,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "fake.env"
    path.write_text(payload)
    with pytest.raises(ValueError, match="^credentials_unavailable$"):
        _module().load_alpaca_credentials(path)
    assert not (tmp_path / "SENTINEL").exists()


def test_credential_symlinks_are_refused_without_following_them(tmp_path: Path) -> None:
    target = tmp_path / "fake-target.env"
    target.write_text("APCA_API_KEY_ID=fake\nAPCA_API_SECRET_KEY=fake\n")
    path = tmp_path / "fake-link.env"
    path.symlink_to(target)
    with pytest.raises(ValueError, match="^credentials_unavailable$"):
        _module().load_alpaca_credentials(path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["budget"].update(max_attempts=True),
        lambda d: d["budget"].update(max_elapsed_seconds=float("inf")),
        lambda d: d["stages"][1].update(request_kind="bars"),
        lambda d: d["stages"][1]["request"].update(types=["forward_split"]),
        lambda d: d["stages"][2]["request"].update(symbols=["AAPL"]),
        lambda d: d["stages"][4]["request"].update(start="2020-02-01"),
        lambda d: d["stages"].__setitem__(1, d["stages"][0]),
        lambda d: d.update(calendar_path="\\private\\calendar.json"),
    ],
)
def test_frozen_scope_rejects_ambiguous_or_incompatible_plan_changes(
    tmp_path: Path, mutate
) -> None:
    path = _copy(tmp_path, mutate)
    with pytest.raises(ValueError, match="^invalid_acquisition_plan$"):
        _module().load_acquisition_plan(path)


def test_duplicate_plan_json_keys_are_not_silently_overwritten(tmp_path: Path) -> None:
    path = _copy(tmp_path)
    raw = path.read_text().replace('"feed": "iex"', '"feed": "sip", "feed": "iex"', 1)
    path.write_text(raw)
    with pytest.raises(ValueError, match="^invalid_acquisition_plan$"):
        _module().load_acquisition_plan(path)


def test_plan_and_calendar_identity_are_preserved_without_mutation(tmp_path: Path) -> None:
    import hashlib

    path = _copy(tmp_path)
    before = path.read_bytes()
    registered = _module().load_acquisition_plan(path)
    assert registered.raw_bytes == before
    assert registered.sha256 == hashlib.sha256(before).hexdigest()
    assert registered.calendar.sha256 == registered.plan.calendar_sha256
    assert path.read_bytes() == before
