"""Hand-calculated synthetic accounting regressions; no provider or broker I/O."""

from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

import pytest

from packages.backtesting import corporate_actions as accounting
from packages.data import corporate_actions as models

EX_DATE = date(2024, 6, 10)
PAY_DATE = date(2024, 6, 15)  # Saturday; first later processed session receives the cash.
OPEN = datetime(2024, 6, 10, 13, 30, tzinfo=UTC)
ANNOUNCED = datetime(2024, 6, 3, 12, 0, tzinfo=UTC)


def _split(**changes):
    return models.SplitAction(
        **{
            "action_id": "split-1",
            "security_id": "security-abc",
            "symbol": "ABC",
            "ex_date": EX_DATE,
            "available_at": ANNOUNCED,
            "availability_basis": "synthetic",
            "numerator": 4,
            "denominator": 1,
            **changes,
        }
    )


def _dividend(**changes):
    return models.CashDividendAction(
        **{
            "action_id": "dividend-1",
            "security_id": "security-abc",
            "symbol": "ABC",
            "ex_date": EX_DATE,
            "pay_date": PAY_DATE,
            "available_at": ANNOUNCED,
            "availability_basis": "synthetic",
            "cash_per_share": Decimal("0.50"),
            **changes,
        }
    )


def _state(*, quantity="3", **changes):
    return accounting.PortfolioActionState(
        **{
            "cash": Decimal("100"),
            "positions": (
                accounting.AccountingPosition(
                    security_id="security-abc",
                    symbol="ABC",
                    quantity=Decimal(quantity),
                    cost_basis=Decimal("240") if Decimal(quantity) else Decimal("0"),
                    stop_price=Decimal("60"),
                ),
            ),
            **changes,
        }
    )


@pytest.mark.parametrize(
    ("numerator", "quantity", "stop", "order_quantity", "limit"),
    [(4, "12", "15", "8", "20"), (10, "30", "6", "20", "8")],
)
def test_forward_splits_preserve_total_cost_and_scale_positions_and_pending_orders(
    numerator, quantity, stop, order_quantity, limit
):
    order = accounting.PendingOrder(
        order_id="buy-1",
        security_id="security-abc",
        symbol="ABC",
        quantity=Decimal("2"),
        limit_price=Decimal("80"),
        stop_price=Decimal("64"),
    )
    before = _state(pending_orders=(order,))
    after = accounting.apply_session_actions(
        before, (_split(numerator=numerator),), session=EX_DATE, as_of=OPEN
    )
    assert after.positions[0].quantity == Decimal(quantity)
    assert after.positions[0].cost_basis == Decimal("240")
    assert after.positions[0].stop_price == Decimal(stop)
    assert after.pending_orders[0].quantity == Decimal(order_quantity)
    assert after.pending_orders[0].limit_price == Decimal(limit)
    assert after.pending_orders[0].stop_price == Decimal("64") / Decimal(numerator)
    assert after.cash == Decimal("100")
    assert before.positions[0].quantity == Decimal("3")


def test_reverse_split_rejects_fractional_holding_without_changing_input():
    before = _state()
    with pytest.raises(ValueError, match="fractional_quantity"):
        accounting.apply_session_actions(
            before, (_split(numerator=1, denominator=4),), session=EX_DATE, as_of=OPEN
        )
    assert before.positions[0].quantity == Decimal("3")
    assert before.applied_actions == ()


def test_exact_fractional_policy_keeps_fraction_and_all_cost_basis():
    after = accounting.apply_session_actions(
        _state(),
        (_split(numerator=1, denominator=4),),
        session=EX_DATE,
        as_of=OPEN,
        fractional_policy="exact",
    )
    assert after.positions[0].quantity == Decimal("0.75")
    assert after.positions[0].cost_basis == Decimal("240")
    assert after.positions[0].stop_price == Decimal("240")
    assert after.cash == Decimal("100")


def test_fractional_pending_order_is_rejected_even_without_a_holding():
    order = accounting.PendingOrder(
        order_id="pending", security_id="security-abc", symbol="ABC", quantity=Decimal("3")
    )
    with pytest.raises(ValueError, match="fractional_quantity"):
        accounting.apply_session_actions(
            _state(positions=(), pending_orders=(order,)),
            (_split(numerator=1, denominator=4),),
            session=EX_DATE,
            as_of=OPEN,
        )


def test_cash_in_lieu_is_explicitly_unsupported():
    with pytest.raises(ValueError, match="unsupported_fractional_policy"):
        accounting.apply_session_actions(
            _state(), (), session=EX_DATE, as_of=OPEN, fractional_policy="cash_in_lieu"
        )


def test_dividend_entitlement_is_prior_close_quantity_and_cash_waits_for_payment():
    entitled = accounting.apply_session_actions(
        _state(), (_dividend(),), session=EX_DATE, as_of=OPEN
    )
    assert entitled.cash == Decimal("100")
    assert entitled.entitlements[0].quantity == Decimal("3")
    assert entitled.entitlements[0].cash_amount == Decimal("1.50")
    assert not entitled.entitlements[0].paid
    # The whole holding was sold on ex-date. The entitlement survives the sale.
    sold = entitled.model_copy(update={"positions": ()})
    before_pay = accounting.apply_session_actions(
        sold,
        (_dividend(),),
        session=date(2024, 6, 14),
        as_of=datetime(2024, 6, 14, 13, 30, tzinfo=UTC),
    )
    assert before_pay.cash == Decimal("100")
    paid = accounting.apply_session_actions(
        before_pay,
        (_dividend(),),
        session=date(2024, 6, 17),
        as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
    )
    assert paid.cash == Decimal("101.50")
    assert paid.entitlements[0].paid
    repeated = accounting.apply_session_actions(
        paid,
        (_dividend(),),
        session=date(2024, 6, 17),
        as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
    )
    assert repeated.cash == Decimal("101.50")
    assert repeated == paid


def test_ex_date_buyer_has_zero_entitlement_even_when_shares_exist_at_payment():
    entitled = accounting.apply_session_actions(
        _state(positions=()), (_dividend(),), session=EX_DATE, as_of=OPEN
    )
    assert entitled.entitlements[0].quantity == Decimal("0")
    bought = entitled.model_copy(update={"positions": _state().positions})
    paid = accounting.apply_session_actions(
        bought,
        (_dividend(),),
        session=date(2024, 6, 17),
        as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
    )
    assert paid.cash == Decimal("100")
    assert paid.entitlements[0].cash_amount == Decimal("0")


def test_same_date_split_precedes_dividend_using_post_split_per_share_amount():
    actions = (_dividend(pay_date=EX_DATE), _split())
    after = accounting.apply_session_actions(_state(), actions, session=EX_DATE, as_of=OPEN)
    assert after.positions[0].quantity == Decimal("12")
    assert after.entitlements[0].quantity == Decimal("12")
    assert after.cash == Decimal("106.00")
    reverse = accounting.apply_session_actions(
        _state(), tuple(reversed(actions)), session=EX_DATE, as_of=OPEN
    )
    assert after == reverse


def test_zero_position_stays_zero_and_has_zero_dividend_credit():
    after = accounting.apply_session_actions(
        _state(quantity="0"),
        (_split(), _dividend(pay_date=EX_DATE)),
        session=EX_DATE,
        as_of=OPEN,
    )
    assert after.positions[0].quantity == 0
    assert after.positions[0].cost_basis == 0
    assert after.cash == Decimal("100")


def test_identical_repeat_is_idempotent_but_changed_applied_payload_fails():
    after = accounting.apply_session_actions(_state(), (_split(),), session=EX_DATE, as_of=OPEN)
    assert (
        accounting.apply_session_actions(after, (_split(),), session=EX_DATE, as_of=OPEN) == after
    )
    with pytest.raises(ValueError, match="applied_action_changed"):
        accounting.apply_session_actions(
            after, (_split(numerator=10),), session=EX_DATE, as_of=OPEN
        )


def test_future_action_does_not_change_earlier_state():
    state = accounting.apply_session_actions(
        _state(),
        (_split(ex_date=date(2024, 6, 11), available_at=datetime(2024, 6, 11, tzinfo=UTC)),),
        session=EX_DATE,
        as_of=OPEN,
    )
    assert state.positions[0].quantity == Decimal("3")
    assert state.applied_actions == ()


def test_due_but_unavailable_action_fails_closed():
    with pytest.raises(ValueError, match="action_unavailable"):
        accounting.apply_session_actions(
            _state(),
            (_split(available_at=datetime(2024, 6, 10, 14, 0, tzinfo=UTC)),),
            session=EX_DATE,
            as_of=OPEN,
        )


def test_session_must_advance_without_skipping_unapplied_action_or_going_backwards():
    initial = accounting.apply_session_actions(_state(), (), session=EX_DATE, as_of=OPEN)
    with pytest.raises(ValueError, match="backwards_session"):
        accounting.apply_session_actions(
            initial, (), session=date(2024, 6, 7), as_of=datetime(2024, 6, 7, 13, 30, tzinfo=UTC)
        )
    with pytest.raises(ValueError, match="missed_ex_date"):
        accounting.apply_session_actions(
            initial,
            (_split(),),
            session=date(2024, 6, 11),
            as_of=datetime(2024, 6, 11, 13, 30, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="session_already_processed"):
        accounting.apply_session_actions(initial, (_split(),), session=EX_DATE, as_of=OPEN)


def test_wrong_position_identity_is_not_adjusted_by_symbol_only():
    conflicting = _split(symbol="OLD")
    with pytest.raises(ValueError, match="security_symbol_mismatch"):
        accounting.apply_session_actions(_state(), (conflicting,), session=EX_DATE, as_of=OPEN)


def test_decimal_arithmetic_uses_fixed_precision_and_refuses_inexact_results():
    with localcontext() as context:
        context.prec = 3
        after = accounting.apply_session_actions(
            _state(quantity="1234"), (_split(),), session=EX_DATE, as_of=OPEN
        )
    assert after.positions[0].quantity == Decimal("4936")
    with pytest.raises(ValueError, match="inexact_decimal"):
        accounting.apply_session_actions(
            _state(),
            (_split(numerator=7, denominator=1),),
            session=EX_DATE,
            as_of=OPEN,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"action_id": ""},
        {"security_id": ""},
        {"symbol": "abc"},
        {"available_at": datetime(2024, 6, 3)},
        {"availability_basis": "unknown"},
        {"numerator": 0},
        {"denominator": -1},
        {"numerator": 4.0},
        {"numerator": True},
        {"numerator": 1, "denominator": 1},
    ],
)
def test_invalid_split_evidence_is_rejected(changes):
    with pytest.raises(ValueError):
        _split(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_per_share": "NaN"},
        {"cash_per_share": "Infinity"},
        {"cash_per_share": "-1"},
        {"cash_per_share": "0"},
        {"cash_per_share": 0.1},
        {"currency": "EUR"},
        {"pay_date": date(2024, 6, 7)},
        {"share_basis": "pre_split"},
    ],
)
def test_invalid_or_unsupported_dividend_evidence_is_rejected(changes):
    with pytest.raises(ValueError):
        _dividend(**changes)


def test_duplicate_or_contradictory_action_records_are_rejected():
    for actions in (
        (_split(), _split()),
        (_split(), _split(action_id="another-id", numerator=10)),
        (_split(), _dividend(action_id="split-1")),
    ):
        with pytest.raises(ValueError, match="duplicate|conflicting"):
            models.validate_actions(actions)
        with pytest.raises(ValueError, match="duplicate|conflicting"):
            accounting.apply_session_actions(_state(), actions, session=EX_DATE, as_of=OPEN)


def test_missing_required_action_fields_fail_before_accounting():
    with pytest.raises(ValueError):
        models.CashDividendAction.model_validate(
            {"kind": "cash_dividend", "symbol": "ABC", "ex_date": EX_DATE}
        )


def test_same_symbol_with_different_security_identity_fails_closed():
    with pytest.raises(ValueError, match="security_symbol_mismatch"):
        accounting.apply_session_actions(
            _state(),
            (_split(security_id="another-security"),),
            session=EX_DATE,
            as_of=OPEN,
        )


def test_later_split_preserves_existing_cash_dividend_receivable():
    after_ex = accounting.apply_session_actions(
        _state(), (_dividend(),), session=EX_DATE, as_of=OPEN
    )
    after_split = accounting.apply_session_actions(
        after_ex,
        (_dividend(), _split(ex_date=date(2024, 6, 11))),
        session=date(2024, 6, 11),
        as_of=datetime(2024, 6, 11, 13, 30, tzinfo=UTC),
    )
    assert after_split.positions[0].quantity == Decimal("12")
    assert after_split.entitlements[0].quantity == Decimal("3")
    assert after_split.entitlements[0].cash_amount == Decimal("1.50")


def test_dividend_receivable_preserves_equity_across_ex_date_price_drop():
    after = accounting.apply_session_actions(_state(), (_dividend(),), session=EX_DATE, as_of=OPEN)
    assert after.cash + after.positions[0].quantity * Decimal("79.50") + sum(
        (item.cash_amount for item in after.entitlements if not item.paid), Decimal(0)
    ) == Decimal("340")


def test_replayed_decimal_value_with_different_trailing_zeros_is_identical():
    original = accounting.apply_session_actions(
        _state(), (_dividend(),), session=EX_DATE, as_of=OPEN
    )
    replayed = accounting.apply_session_actions(
        original, (_dividend(cash_per_share="0.5"),), session=EX_DATE, as_of=OPEN
    )
    assert replayed == original


def test_naive_cutoff_cannot_authorize_actions():
    with pytest.raises(ValueError, match="cutoff_requires_offset"):
        accounting.apply_session_actions(
            _state(), (_split(),), session=EX_DATE, as_of=datetime(2024, 6, 10, 13, 30)
        )


def test_duplicate_holdings_or_orders_cannot_duplicate_entitlement_or_split():
    position = _state().positions[0]
    with pytest.raises(ValueError, match="duplicate_position"):
        accounting.PortfolioActionState(cash="0", positions=(position, position))
    order = accounting.PendingOrder(
        order_id="one-order", security_id="security-abc", symbol="ABC", quantity="1"
    )
    with pytest.raises(ValueError, match="duplicate_order"):
        accounting.PortfolioActionState(cash="0", pending_orders=(order, order))


def test_zero_holding_cannot_hide_nonzero_cost_basis():
    with pytest.raises(ValueError, match="zero_position_has_cost_basis"):
        accounting.AccountingPosition(
            security_id="security-abc", symbol="ABC", quantity="0", cost_basis="1"
        )


def test_canonical_action_order_is_stable_and_declaration_must_precede_availability():
    ordered = models.validate_actions(
        (_dividend(), _split(security_id="security-z", symbol="ZZZ", action_id="z"), _split())
    )
    assert tuple(action.action_id for action in ordered) == ("split-1", "z", "dividend-1")
    with pytest.raises(ValueError, match="availability_precedes_declaration"):
        _dividend(declared_at=datetime(2024, 6, 4, tzinfo=UTC))


def _entitled_state():
    return accounting.apply_session_actions(_state(), (_dividend(),), session=EX_DATE, as_of=OPEN)


def test_complete_inventory_must_include_every_previously_applied_action():
    with pytest.raises(ValueError, match="missing_applied_action"):
        accounting.apply_session_actions(
            _entitled_state(),
            (),
            session=date(2024, 6, 17),
            as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("security_id", "wrong-security"),
        ("symbol", "WRONG"),
        ("ex_date", date(2024, 6, 7)),
        ("pay_date", date(2024, 6, 18)),
        ("quantity", Decimal("4")),
        ("cash_amount", Decimal("200")),
        ("paid", True),
    ],
)
def test_restored_entitlement_must_match_action_amount_identity_and_payment_timeline(field, value):
    state = _entitled_state()
    corrupt = state.model_copy(
        update={"entitlements": (state.entitlements[0].model_copy(update={field: value}),)}
    )
    with pytest.raises(ValueError, match="invalid_entitlement"):
        accounting.apply_session_actions(
            corrupt,
            (_dividend(),),
            session=date(2024, 6, 17),
            as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
        )


def test_applied_dividend_requires_its_entitlement_record():
    corrupt = _entitled_state().model_copy(update={"entitlements": ()})
    with pytest.raises(ValueError, match="missing_dividend_entitlement"):
        accounting.apply_session_actions(corrupt, (_dividend(),), session=EX_DATE, as_of=OPEN)


def test_split_action_cannot_authorize_a_cash_entitlement():
    state = accounting.apply_session_actions(_state(), (_split(),), session=EX_DATE, as_of=OPEN)
    fake = accounting.DividendEntitlement(
        action_id="split-1",
        security_id="security-abc",
        symbol="ABC",
        ex_date=EX_DATE,
        pay_date=EX_DATE,
        quantity="3",
        cash_amount="99",
    )
    corrupt = state.model_copy(update={"entitlements": (fake,)})
    with pytest.raises(ValueError, match="non_dividend_entitlement"):
        accounting.apply_session_actions(corrupt, (_split(),), session=EX_DATE, as_of=OPEN)


def test_orphan_entitlement_cannot_authorize_cash_credit():
    corrupt = _entitled_state().model_copy(update={"applied_actions": ()})
    with pytest.raises(ValueError, match="orphan_entitlement"):
        accounting.apply_session_actions(
            corrupt,
            (_dividend(),),
            session=date(2024, 6, 17),
            as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
        )


def test_restored_ledger_requires_a_last_session_and_completed_due_payments():
    state = _entitled_state()
    for corrupt in (
        state.model_copy(update={"last_session": None}),
        state.model_copy(update={"last_session": date(2024, 6, 17)}),
    ):
        with pytest.raises(ValueError, match="restored_state_timeline|invalid_entitlement"):
            accounting.apply_session_actions(
                corrupt,
                (_dividend(),),
                session=date(2024, 6, 18),
                as_of=datetime(2024, 6, 18, 13, 30, tzinfo=UTC),
            )


def test_restored_action_cannot_have_been_applied_before_its_ex_date():
    state = accounting.apply_session_actions(_state(), (_split(),), session=EX_DATE, as_of=OPEN)
    future = _split(ex_date=date(2024, 6, 11))
    corrupt = state.model_copy(
        update={
            "applied_actions": (
                accounting.AppliedAction(
                    action_id=future.action_id,
                    fingerprint=models.corporate_action_fingerprint(future),
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="restored_state_timeline"):
        accounting.apply_session_actions(
            corrupt,
            (future,),
            session=date(2024, 6, 11),
            as_of=datetime(2024, 6, 11, 13, 30, tzinfo=UTC),
        )


def test_future_cutoff_cannot_authorize_action_in_an_earlier_session():
    with pytest.raises(ValueError, match="cutoff_session_mismatch"):
        accounting.apply_session_actions(
            _state(),
            (_split(available_at=datetime(2024, 6, 11, tzinfo=UTC)),),
            session=EX_DATE,
            as_of=datetime(2024, 6, 11, 13, 30, tzinfo=UTC),
        )


def test_later_ten_for_one_split_preserves_ex_date_dividend_dollars():
    first_actions = (_split(), _dividend())
    after_ex = accounting.apply_session_actions(
        _state(), first_actions, session=EX_DATE, as_of=OPEN
    )
    assert after_ex.entitlements[0].cash_amount == Decimal("6.00")
    later = _split(action_id="later-ten", ex_date=date(2024, 6, 11), numerator=10)
    complete = (*first_actions, later)
    after_ten = accounting.apply_session_actions(
        after_ex,
        complete,
        session=date(2024, 6, 11),
        as_of=datetime(2024, 6, 11, 13, 30, tzinfo=UTC),
    )
    assert after_ten.positions[0].quantity == Decimal("120")
    assert after_ten.positions[0].cost_basis == Decimal("240")
    assert after_ten.positions[0].stop_price == Decimal("1.5")
    assert after_ten.entitlements[0].quantity == Decimal("12")
    assert after_ten.entitlements[0].cash_amount == Decimal("6.00")
    paid = accounting.apply_session_actions(
        after_ten,
        complete,
        session=date(2024, 6, 17),
        as_of=datetime(2024, 6, 17, 13, 30, tzinfo=UTC),
    )
    assert paid.cash == Decimal("106.00")


def test_accounting_does_not_inherit_callers_decimal_exponent_limits():
    with localcontext() as context:
        context.Emax = 2
        after = accounting.apply_session_actions(
            _state(quantity="1234"), (_split(),), session=EX_DATE, as_of=OPEN
        )
    assert after.positions[0].quantity == Decimal("4936")


def test_fingerprint_uses_bounded_memory_for_compact_decimal_exponents():
    import tracemalloc

    action = _dividend(cash_per_share="1e100000")
    equivalent = _dividend(cash_per_share="10e99999")
    with localcontext() as context:
        context.prec = 2
        context.Emax = 10
        tracemalloc.start()
        try:
            fingerprint = models.corporate_action_fingerprint(action)
            replayed = models.corporate_action_fingerprint(equivalent)
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert fingerprint == replayed
    assert peak_bytes < 50_000
