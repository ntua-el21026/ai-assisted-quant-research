"""Optional CLI and private publication use original synthetic responses only."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from test_acquisition_session import run


def api():
    try:
        return importlib.import_module("packages.data.requalification_cli")
    except ModuleNotFoundError:
        pytest.fail("requalification CLI implementation missing")


def test_no_credentials_or_network_without_explicit_opt_in(tmp_path):
    module = api()
    with patch.object(module, "load_alpaca_credentials") as credentials:
        assert (
            module.main(
                [
                    "acquire",
                    "--policy",
                    str(tmp_path / "policy.json"),
                    "--workspace",
                    str(tmp_path / "output"),
                    "--credentials-file",
                    str(tmp_path / "private.env"),
                ]
            )
            == 2
        )
    credentials.assert_not_called()


def test_offline_publication_repeats_bytes_and_cannot_overwrite(tmp_path):
    module = api()
    original, _, workspace = run(tmp_path)
    inputs = SimpleNamespace(sha256="1" * 64)
    with patch.object(
        module,
        "build_requalification_report",
        return_value={
            "schema_version": "historical-requalification/v1",
            "dataset_to_r4c": "BLOCKED",
            "technical_pilot": "PASS",
            "synthetic": True,
        },
    ):
        one = module.qualify_requalified(
            original.manifest_path,
            inputs,
            repository=workspace.parents[3],
            output=workspace / "new-one",
        )
        two = module.qualify_requalified(
            original.manifest_path,
            inputs,
            repository=workspace.parents[3],
            output=workspace / "new-two",
        )
        with pytest.raises(Exception, match="private_storage_exists"):
            module.qualify_requalified(
                original.manifest_path,
                inputs,
                repository=workspace.parents[3],
                output=workspace / "new-one",
            )
    assert one["hashes"] == two["hashes"]
    assert (workspace / "new-one/report/requalification.json").read_bytes() == (
        workspace / "new-two/report/requalification.json"
    ).read_bytes()


def test_private_scope_is_required_even_for_qualification(tmp_path):
    module = api()
    original, _, workspace = run(tmp_path)
    with pytest.raises(Exception, match="private_storage_path"):
        module.qualify_requalified(
            original.manifest_path,
            SimpleNamespace(sha256="1" * 64),
            repository=workspace.parents[3],
            output=tmp_path / "public",
        )
