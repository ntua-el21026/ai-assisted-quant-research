"""Exact typed acquisition-to-v2 conversion; no transport, storage or credential discovery."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal

from packages.data.alpaca_historical import (
    CorporateActionsRequest,
    HistoricalAcquisition,
    HistoricalAcquisitionError,
    HistoricalBarsRequest,
    decode_historical_page,
    historical_query,
)
from packages.data.alpaca_historical import (
    HistoricalBar as AcquiredBar,
)
from packages.data.historical_models import AcquisitionProvenance, HistoricalBar


class HistoricalNormalizationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def to_snapshot_bar(
    observation: AcquiredBar,
    *,
    security_id: str,
    acquisition_id: str,
    mocked: bool,
) -> HistoricalBar:
    """Require caller-owned security identity; preserve original exact source values.

    The mock label changes the evidence class to synthetic. Ordinary conversion
    preserves observed versus explicitly assumed availability without backdating.
    """
    if observation.adjustment != "raw" or observation.bar.adjusted:
        raise HistoricalNormalizationError("raw_execution_required")
    return HistoricalBar(
        security_id=security_id,
        symbol=observation.bar.symbol,
        date=observation.bar.date,
        **observation.exact_ohlcv.model_dump(),
        available_at=observation.available_at,
        availability_basis="synthetic" if mocked else observation.availability_basis,
        acquisition_id=acquisition_id,
    )


def _query_hash(query: Mapping[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(dict(query), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _completed_query_chain(acquisition: HistoricalAcquisition) -> tuple[str, ...]:
    endpoint, expected = historical_query(acquisition.request)
    if not acquisition.pages or len(acquisition.pages) > acquisition.request.max_pages:
        raise HistoricalNormalizationError("invalid_pagination_chain")
    started = acquisition.request_started_at
    finished = acquisition.acquired_at
    if started.utcoffset() is None or finished.utcoffset() is None or started > finished:
        raise HistoricalNormalizationError("invalid_acquisition_times")
    previous = started
    for page in acquisition.pages:
        if page.received_at.utcoffset() is None or not previous <= page.received_at <= finished:
            raise HistoricalNormalizationError("invalid_acquisition_times")
        previous = page.received_at
    if previous != finished:
        raise HistoricalNormalizationError("invalid_acquisition_times")
    token: str | None = None
    seen: set[str] = set()
    hashes = []
    for index, page in enumerate(acquisition.pages):
        query = dict(page.query)
        if len(query) != len(page.query) or page.endpoint != endpoint:
            raise HistoricalNormalizationError("invalid_acquisition_query")
        if query.pop("page_token", None) != token:
            raise HistoricalNormalizationError("invalid_pagination_chain")
        if query != expected:
            raise HistoricalNormalizationError("invalid_acquisition_query")
        try:
            payload = decode_historical_page(page.body)
        except HistoricalAcquisitionError:
            raise HistoricalNormalizationError("invalid_pagination_chain") from None
        data_key = (
            "bars"
            if isinstance(acquisition.request, HistoricalBarsRequest)
            else "corporate_actions"
        )
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get(data_key), dict)
            or "next_page_token" not in payload
        ):
            raise HistoricalNormalizationError("invalid_pagination_chain")
        next_token = payload["next_page_token"]
        if next_token is not None:
            if (
                not isinstance(next_token, str)
                or not next_token
                or len(next_token) > 4096
                or next_token in seen
            ):
                raise HistoricalNormalizationError("invalid_pagination_chain")
            seen.add(next_token)
        token = next_token
        if (token is None) != (index == len(acquisition.pages) - 1):
            raise HistoricalNormalizationError("invalid_pagination_chain")
        hashes.append(_query_hash(dict(page.query)))
    return tuple(hashes)


def to_acquisition_provenance(
    acquisition: HistoricalAcquisition,
    *,
    acquisition_id: str,
    mocked: bool,
) -> AcquisitionProvenance:
    """Bind full wire parameters and exhausted pagination to a v2 receipt.

    Completion concerns this exact query; it does not attest action ex-date
    coverage, licensing, historical publication times or provider revision truth.
    """
    request = acquisition.request
    if isinstance(request, HistoricalBarsRequest) and request.adjustment != "raw":
        raise HistoricalNormalizationError("raw_execution_required")
    if isinstance(request, CorporateActionsRequest) and request.types != "all":
        raise HistoricalNormalizationError("filtered_action_inventory")
    page_hashes = _completed_query_chain(acquisition)
    _, query = historical_query(request)
    bars = isinstance(request, HistoricalBarsRequest)
    endpoint_path: Literal["/v2/stocks/bars", "/v1/corporate-actions"] = (
        "/v2/stocks/bars" if bars else "/v1/corporate-actions"
    )
    return AcquisitionProvenance(
        acquisition_id=acquisition_id,
        provider="synthetic" if mocked else "alpaca",
        mocked=mocked,
        endpoint=endpoint_path,
        symbols=request.symbols,
        feed=request.feed if isinstance(request, HistoricalBarsRequest) else None,
        adjustment="raw" if bars else None,
        timeframe="1Day" if bars else None,
        start=request.start,
        end=request.end,
        asof=request.asof if isinstance(request, HistoricalBarsRequest) else None,
        currency="USD" if bars else None,
        request_started_at=acquisition.request_started_at,
        acquired_at=acquisition.acquired_at,
        page_sha256=tuple(p.sha256 for p in acquisition.pages),
        complete=True,
        action_scope=None if bars else "all",
        query_parameters=tuple(sorted(query.items())),
        page_query_sha256=page_hashes,
    )
