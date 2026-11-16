"""Independent literal action-aware benchmark arithmetic and timing fixtures."""

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal, localcontext
from importlib import import_module
from types import SimpleNamespace

import pytest

from packages.data.corporate_actions import CashDividendAction, SplitAction

DATES = tuple(date(2024, 3, day) for day in (8, 11, 12, 13, 14, 15))
SECURITY = "synthetic:001"


def _api():
    return import_module("packages.research.historical_benchmarks")


def _fixture(*, actions=True):
    sessions = tuple(
        SimpleNamespace(
            date=d,
            open_at=datetime.combine(d, time(14, 30), UTC),
            close_at=datetime.combine(d, time(21), UTC),
        )
        for d in DATES
    )
    bars = tuple(
        SimpleNamespace(
            security_id=SECURITY,
            symbol="SYN",
            date=d,
            open=Decimal(price),
            high=Decimal(price),
            low=Decimal(price),
            close=Decimal(price),
            volume=Decimal("10000"),
            available_at=s.close_at,
            availability_basis="synthetic",
            acquisition_id="original-synthetic",
        )
        for d, s, price in zip(
            DATES, sessions, ("400", "100", "99", "9.9", "10", "11"), strict=True
        )
    )
    announced = datetime(2024, 3, 1, tzinfo=UTC)
    common = dict(
        security_id=SECURITY, symbol="SYN", available_at=announced,
        availability_basis="synthetic",
    )
    events = (
        SplitAction(action_id="split-four", ex_date=DATES[1], numerator=4, denominator=1, **common),
        CashDividendAction(
            action_id="dividend", ex_date=DATES[2], pay_date=DATES[4],
            cash_per_share=Decimal("1"), **common,
        ),
        SplitAction(action_id="split-ten", ex_date=DATES[3], numerator=10, denominator=1, **common),
    ) if actions else ()
    return SimpleNamespace(
        manifest=SimpleNamespace(
            execution_price_basis="raw", currency="USD", sessions=sessions,
            securities=(SimpleNamespace(security_id=SECURITY),),
        ),
        manifest_sha256="1" * 64, raw_bars=bars, actions=events,
    )


def _evaluate(snapshot=None, convention="price_return", **kwargs):
    return _api().evaluate_historical_benchmark(
        snapshot or _fixture(), SECURITY, Decimal("1000"), convention=convention, **kwargs
    )


@pytest.mark.parametrize(
    ("convention", "equity", "cash", "quantity", "cost"),
    [
        ("price_return", "1100", "0", "100", "1000"),
        ("total_return_cash", "1110", "10", "100", "1000"),
        ("total_return_reinvest", "1111", "0", "101", "1010"),
    ],
)
def test_split_and_cash_dividend_return_conventions_have_literal_terminal_values(
    convention, equity, cash, quantity, cost
):
    result = _evaluate(convention=convention)
    final = result.points[-1]
    assert (final.equity, final.cash, final.quantity, final.cost_basis) == tuple(
        Decimal(value) for value in (equity, cash, quantity, cost)
    )
    assert final.dividend_receivable == 0
    assert result.conventions.return_convention == convention
    for point in result.points:
        assert point.equity == point.cash + point.dividend_receivable + point.market_value


def test_ex_date_receivable_survives_later_split_and_only_becomes_cash_on_payment():
    result = _evaluate(convention="total_return_cash")
    before, ex, split, pay = result.points[1:5]
    assert (before.quantity, before.equity, before.dividend_receivable) == (
        Decimal("10"), Decimal("1000"), Decimal("0")
    )
    assert (ex.quantity, ex.market_value, ex.dividend_receivable, ex.equity, ex.cash) == (
        Decimal("10"), Decimal("990"), Decimal("10"), Decimal("1000"), Decimal("0")
    )
    assert (split.quantity, split.dividend_receivable, split.cost_basis) == (
        Decimal("100"), Decimal("10"), Decimal("1000")
    )
    assert (pay.cash, pay.dividend_receivable, pay.equity) == (
        Decimal("10"), Decimal("0"), Decimal("1010")
    )


def test_reinvestment_uses_payment_open_and_never_payment_close():
    snapshot = _fixture()
    # Payment opens at 20 and closes at 24; 10 cash buys .5 share at the open.
    snapshot.raw_bars = tuple(
        SimpleNamespace(**{**vars(bar), "open": Decimal("20"), "high": Decimal("24"),
                           "low": Decimal("20"), "close": Decimal("24")})
        if bar.date == DATES[4] else bar for bar in snapshot.raw_bars
    )
    paid = _evaluate(snapshot, convention="total_return_reinvest").points[4]
    assert paid.quantity == Decimal("100.5")
    assert paid.reinvested_cash == Decimal("10")
    assert paid.market_value == Decimal("2412")
    assert paid.cash == 0


def test_non_session_payment_reinvests_at_first_later_calendar_open():
    snapshot = _fixture()
    snapshot.actions = tuple(
        action.model_copy(update={"pay_date": date(2024, 3, 16)})
        if isinstance(action, CashDividendAction)
        else action for action in snapshot.actions
    )
    later = date(2024, 3, 18)
    session = SimpleNamespace(
        date=later,
        open_at=datetime.combine(later, time(14, 30), UTC),
        close_at=datetime.combine(later, time(21), UTC),
    )
    snapshot.manifest.sessions = (*snapshot.manifest.sessions, session)
    snapshot.raw_bars = (*snapshot.raw_bars, SimpleNamespace(
        **{**vars(snapshot.raw_bars[-1]), "date": later, "open": Decimal("20"),
           "high": Decimal("24"), "low": Decimal("20"), "close": Decimal("24"),
           "available_at": session.close_at}
    ))
    result = _evaluate(snapshot, convention="total_return_reinvest")
    assert result.points[-2].dividend_receivable == Decimal("10")
    assert result.points[-2].reinvested_cash == 0
    assert result.points[-1].quantity == Decimal("100.5")
    assert result.points[-1].reinvested_cash == Decimal("10")


def test_same_date_split_then_dividend_entitlement_precedes_reinvestment():
    snapshot = _fixture()
    snapshot.actions = (
        snapshot.actions[1].model_copy(update={"ex_date": DATES[1], "pay_date": DATES[1]}),
        snapshot.actions[0],
    )
    point = _evaluate(snapshot, convention="total_return_reinvest").points[1]
    assert point.quantity == Decimal("10.1")
    assert point.reinvested_cash == Decimal("10")
    assert point.cost_basis == Decimal("1010")


def test_initial_ex_date_purchase_has_no_dividend_entitlement():
    snapshot = _fixture()
    snapshot.actions = (snapshot.actions[1].model_copy(update={"ex_date": DATES[0]}),)
    result = _evaluate(snapshot, convention="total_return_cash")
    assert all(point.cash == point.dividend_receivable == 0 for point in result.points)


def test_action_free_analytical_benchmark_keeps_first_open_to_close_and_fractional_units():
    snapshot = _fixture(actions=False)
    snapshot.raw_bars = tuple(
        SimpleNamespace(**{**vars(bar), "open": Decimal("100"), "high": Decimal("120"),
                           "low": Decimal("90"), "close": Decimal("110")})
        for bar in snapshot.raw_bars
    )
    for convention in ("price_return", "total_return_cash", "total_return_reinvest"):
        result = _evaluate(snapshot, convention=convention)
        assert all(point.quantity == 10 and point.equity == 1100 for point in result.points)
        assert result.total_return == Decimal("0.1")


def test_recurring_fractional_units_are_context_independent_and_valuation_is_conserved():
    snapshot = _fixture(actions=False)
    snapshot.raw_bars = tuple(
        SimpleNamespace(**{**vars(bar), "open": Decimal("3"), "high": Decimal("6"),
                           "low": Decimal("3"), "close": Decimal("6")})
        for bar in snapshot.raw_bars
    )
    with localcontext() as context:
        context.prec = 3
        result = _evaluate(snapshot)
    assert result.points[-1].equity == Decimal("2000")
    assert result.total_return == 1
    assert len(result.points[0].quantity.as_tuple().digits) == 50


@pytest.mark.parametrize("mutation", ["adjusted", "currency", "missing", "duplicate", "unknown"])
def test_incompatible_or_incomplete_execution_inputs_fail_closed(mutation):
    snapshot = _fixture()
    if mutation == "adjusted":
        snapshot.manifest.execution_price_basis = "split_adjusted"
    elif mutation == "currency":
        snapshot.manifest.currency = "EUR"
    elif mutation == "missing":
        snapshot.raw_bars = snapshot.raw_bars[1:]
    elif mutation == "duplicate":
        snapshot.raw_bars = (*snapshot.raw_bars, snapshot.raw_bars[0])
    else:
        snapshot.raw_bars = (
            SimpleNamespace(**{**vars(snapshot.raw_bars[0]), "security_id": "unknown"}),
            *snapshot.raw_bars[1:],
        )
    with pytest.raises(ValueError):
        _evaluate(snapshot)


@pytest.mark.parametrize("mutation", ["unavailable", "mapping", "non_session", "unknown_security"])
def test_invalid_action_evidence_never_silently_changes_a_benchmark(mutation):
    snapshot = _fixture()
    action = snapshot.actions[0]
    changes = {
        "unavailable": {"available_at": snapshot.manifest.sessions[1].close_at},
        "mapping": {"symbol": "OTHER"},
        "non_session": {"ex_date": date(2024, 3, 10)},
        "unknown_security": {"security_id": "unknown"},
    }[mutation]
    snapshot.actions = (action.model_copy(update=changes), *snapshot.actions[1:])
    with pytest.raises(ValueError):
        _evaluate(snapshot)


def test_requested_calendar_gap_is_rejected_instead_of_skipping_an_entitlement():
    with pytest.raises(ValueError, match="calendar"):
        _evaluate(dates=(DATES[0], DATES[2]))


def test_convention_must_be_explicit_and_comparison_rejects_different_dividend_policies():
    api = _api()
    with pytest.raises(TypeError):
        api.evaluate_historical_benchmark(_fixture(), SECURITY, Decimal("1000"))
    price = _evaluate().conventions
    cash = _evaluate(convention="total_return_cash").conventions
    reinvest = _evaluate(convention="total_return_reinvest").conventions
    api.require_compatible_benchmark_conventions(cash, cash)
    for left, right in ((price, cash), (cash, reinvest)):
        with pytest.raises(ValueError, match="incompatible"):
            api.require_compatible_benchmark_conventions(left, right)
    with pytest.raises(ValueError, match="incompatible"):
        api.require_compatible_benchmark_conventions(cash, replace(cash, currency="EUR"))


def test_reporting_ignores_callers_rounding_and_inexact_traps():
    from decimal import ROUND_DOWN, Inexact

    snapshot = _fixture(actions=False)
    snapshot.raw_bars = tuple(
        SimpleNamespace(**{**vars(bar), "open": Decimal("3"), "high": Decimal("6"),
                           "low": Decimal("3"), "close": Decimal("6")})
        for bar in snapshot.raw_bars
    )
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        result = _evaluate(snapshot)
    assert result.points[0].quantity_rational == "1000/3"
    assert result.points[-1].equity_rational == "2000/1"
    assert result.points[0].quantity == Decimal(
        "333.33333333333333333333333333333333333333333333333"
    )


def test_metadata_states_ignored_dividends_and_explicit_reinvestment_only_when_selected():
    price = _evaluate().conventions
    cash = _evaluate(convention="total_return_cash").conventions
    reinvest = _evaluate(convention="total_return_reinvest").conventions
    assert price.dividend_recognition == "ignored_for_price_return"
    assert price.dividend_payment == "ignored_for_price_return"
    assert price.dividend_reinvestment == cash.dividend_reinvestment == "none"
    assert reinvest.dividend_reinvestment == "payment_open_cash_availability_assumed"


def test_adjusted_row_is_rejected_even_if_manifest_incorrectly_declares_raw_prices():
    snapshot = _fixture()
    snapshot.raw_bars = (
        SimpleNamespace(**{**vars(snapshot.raw_bars[0]), "adjusted": True}),
        *snapshot.raw_bars[1:],
    )
    with pytest.raises(ValueError, match="raw|adjusted"):
        _evaluate(snapshot)


@pytest.mark.parametrize(
    ("convention", "final_equity", "final_units", "final_cash"),
    [
        ("price_return", "1100", "100", "0"),
        ("total_return_cash", "1110", "100", "10"),
        ("total_return_reinvest", "1111", "101", "0"),
    ],
)
def test_verified_v2_snapshot_fixture_preserves_independent_benchmark_arithmetic(
    convention, final_equity, final_units, final_cash
):
    import hashlib
    from pathlib import Path

    from packages.data.historical_snapshots import load_historical_snapshot

    manifest = Path("tests/fixtures/historical_snapshot/manifest.json")
    snapshot = load_historical_snapshot(manifest)
    result = _api().evaluate_historical_benchmark(
        snapshot, SECURITY, Decimal("1000"), convention=convention
    )
    final = result.points[-1]
    assert (final.equity, final.quantity, final.cash) == (
        Decimal(final_equity), Decimal(final_units), Decimal(final_cash)
    )
    assert result.dataset_manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert result.points[2].dividend_receivable == (
        Decimal("0") if convention == "price_return" else Decimal("10")
    )
    assert tuple(point.date for point in result.points) == DATES
