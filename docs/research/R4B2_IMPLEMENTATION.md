# R4-B.2 targeted field resolution — 2026-11-17

**Engineering: PASS. Pilot data: BLOCKED. R4-C readiness: BLOCKED. Independent
acceptance pending.** This checkpoint audits the existing frozen pilot and adds one
optional currency-only helper. It makes no authenticated provider request, changes no
research design, and executes no historical strategy. The [qualification report](R4B2_DATA_QUALIFICATION.md)
contains the admission decision; [verification](R4B2_VERIFICATION.md) records executed checks.

## Baseline and preserved boundaries

The clean canonical `main`, `origin/main` and remote main started at
`5064f7eaae19c0ce97b5f39e17fa84a4a09b7334`. Applicable instructions, v0.7 specification,
protocol, architecture, plans, R4-A contracts, R4-B/B.1 reports, source/tests and pinned
private evidence were inspected. Origin remains
`git@github.com:ntua-el21026/ai-assisted-quant-research.git`.

R1/R2 numerical behavior, R3 workflow/ledger identities, v1/v2 contracts, the strict
normalizer, acquisition plans, action scope and all original evidence remain unchanged.
No new CLI, acquisition mode, provider, framework layer, dependency or snapshot version
is introduced. The candidate remains `historical-candidate/v1`, not admitted v2 data.

## Evidence result and smallest correction

All 16 applicable cash observations lack currency. Independent comparison establishes
16 matching event keys, 15 matching payable dates and eight exactly matching amounts.
QQQ has one payable-date disagreement and eight exact-decimal representation differences;
same-binary64 correspondence does not establish authoritative exact decimal intent.
Current official schemas/changelogs supply no absent-currency-to-USD rule.

The January 2024 SEC-filed SPY prospectus explicitly describes the Trust's Trustee
distributions in USD. Independent issuer records bind the events to that security.
The derived policy is deliberately bounded to **both ex-date and payment within 2024**.
It resolves **three** independent SPY currency fields. A fourth 2024 ex-date event pays
after the 2025 prospectus replacement and remains unresolved, as do all eight QQQ and
four 2025-ex SPY events. The year boundary restricts our interpretation; it is not a
claim that the source policy itself expired on December 31. No dataset period is changed.

The original conservative SPY audit remains immutable, including its earlier zero-resolution
finding. Its extra exact-amount pairing gate on Australian CDI rows was not necessary to
interpret the explicit Trust-level statement. The new receipt uses the U.S. issuer
identity/event matches and that statement. It does not round the Australian amounts or
confuse CDI conversion/payment timing with underlying U.S. distributions.

## Optional interface in the existing reconciliation module

`packages/data/action_reconciliation.py` adds:

- `IndependentCurrencyResolution`: version `independent-currency-resolution/v1`, exact
  original-record hash, explicit currency, policy source hash/reference/publication date,
  declared coverage interval, actual aware observation time and caller interpretation.
- `resolve_independent_currency(record, resolution, *, evidence_documents)` returns a
  derived `IndependentActionRecord` and canonical private receipt bytes. It verifies
  the exact event and policy document bytes, record hash, unknown cash currency, known
  payment date, contemporaneous publication, bounded ex/payment dates and observation
  ordering. Existing currencies cannot be replaced.

The receipt embeds the original record and resolution. Its SHA-256 becomes the derived
record's explicit source identity. Only currency and derived source reference/hash change;
amount, dates, identity and all original records remain unchanged. The caller must retain
the receipt and both source documents. Evidence hashes prove integrity, **not** semantic
correctness of a caller's interpretation. Coverage and identity require human/source review.

No tolerance, date/amount replacement or special-flag override is accepted. The receipt
sets `admitted_v2=false` and `historical_availability_established=false`. Actual observation
time is never backdated to source publication or event dates. The helper is not wired into
the strict provider normalizer, acquisition gate, research runner or R3 workflow. Existing
strict qualifications deliberately continue to use their unchanged original inputs.

## Private audit and deterministic replay

Every original provider row, process date, event date, flag and source hash is preserved.
Separate private SPY/QQQ field matrices inventory all 16 applicable events. A new immutable
partial-resolution context pins their hashes, the pilot manifest, old issuer records and
currency policy. Three record-specific receipts and a 16-record derived independent view
retain the unresolved fields rather than inventing values. No raw provider correction is
claimed. The public report contains match counts and quarter labels, never proprietary
rates, provider identifiers or price observations.

The finite ignored operator calls the tested helper and existing strict qualification
function. Two separate offline processes read the frozen context, reproduce all 11 indexed
audit files exactly, and exclude runtime metadata. Two separate existing qualification
CLI processes reproduce the strict three-file report exactly. The old failed R4-B
qualification is independently recomputed unchanged. These are qualification computations,
not research experiments, and neither promotes a snapshot.

Public source/tests use invented records and policy bytes. New tests first produced
26 missing-interface failures, then passed without changing prior assertions. They cover
exact record/revision binding, altered/missing event and policy bytes, currency conflicts,
unknown payments, ex/payment policy bounds, future policy, aware observation time,
unsupported field overrides, exact Decimal preservation and deterministic receipts.

## Limits and handoff

Currency-only partial evidence does not resolve the pilot's action inventory, remaining
currency, QQQ payment/precision, permanent identity, historical availability/revisions,
execution aggregation or rights restrictions. A venue-price proxy would require separate
approval and evidence; no close-plus-one-minute or auction semantics are asserted.
No 2020–2025 acquisition, strategy run, changed split, empirical chart, performance claim,
credential inspection, broker operation or deployment occurred. Stop after R4-B.2.
