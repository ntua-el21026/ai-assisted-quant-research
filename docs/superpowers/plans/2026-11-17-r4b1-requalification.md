# R4-B.1 corporate-action resolution and requalification plan

**Goal:** establish explicit economic action applicability, preserve the actual QQQ
contradiction, and acquire/qualify the registered pilot within the original aggregate
resource limits. R4-C is excluded. The owner authorizes autonomous execution on main.

**Architecture:** retain every original provider page and the strict R4-A normalizer.
Add a separate, versioned action-scope report and a checkpoint-wide durable budget.
Extend the existing acquisition runner through optional typed hooks for scoped actions,
reused preflight evidence, quota checks and conditional pilot gates. Default R4-B paths
remain unchanged. New offline requalification reports preserve the original full-query
diagnostics alongside economic-scope findings; they never masquerade as admitted v2 data.

**Stack:** existing Python/Pydantic/Pytest/SQLite/Temporal ecosystem, stdlib HTTP/XML,
no new dependencies. Governing specification and protocol remain unchanged in research
hypotheses, dates, thresholds, costs and holdout status.

## Design decisions and evidence before new observations

The clean baseline is `a6d3a0960e5924ab2f2969d02a1620e87b007101`. Original failed
manifest and quality hashes are pinned before reuse. Prior authenticated consumption
is two requests and 1,457 body bytes. It counts toward 100 requests/250 MiB; retained
contents across all private checkpoint workspaces count toward 1 GiB.

The official 2023 Invesco record matches the flagged event's security/ex-date/rate and
reports income/ordinary tax character, while payable dates disagree. Tax character does
not override the provider special flag. No blanket special-distribution support is
scientifically justified by these facts. Further primary evidence may resolve it;
otherwise relevant special events remain rejected.

For the pilot, a **new portfolio begins with independent cash**, no inherited positions,
pending orders or dividend receivables. All execution and feature inputs are raw and
history starts no earlier than 2024-01-01. An otherwise valid cash event whose ex-date
precedes that history has zero eligibility in this portfolio, even if payable afterward.
Both the source event and exclusion reason remain in the scope report. This convention
does not apply to carry-in balances, adjusted inputs, earlier warm-up, splits, identity
changes, mergers or ambiguous events. An ex-date inside 2020–2025 is relevant there.

Use a newly versioned request plan retaining the six original primary request groups,
same symbols/feed/basis/windows, with no early-year or unrelated adjustment diagnostics.
Reuse the pinned original preflight pages rather than requesting them again. Query
only the pilot initially. A larger acquisition requires successful applicable pilot
checks and resolution of known economically relevant action contradictions. It must
not proceed merely because rows or pagination are complete. Unresolved observed-time,
identity, retention and publication limitations remain visible and cannot yield READY.

## Test-first tasks and interfaces

1. `packages/data/action_scope.py`, `tests/unit/test_action_scope.py`:
   `ActionScopeContext`, `classify_action_scope`, private and sanitized serialization,
   `normalize_applicable_actions`. Test fresh/carry-in/receivable/warm-up/adjusted contexts,
   process versus ex/pay time, duplicates, missing/contradictory fields, special in/out
   of period, structural actions, source binding and deterministic ordering. Derived
   selection is internal normalization input, never an invented provider receipt.
2. `packages/data/checkpoint_budget.py`, its tests and backward-compatible optional
   initial counters in `acquisition_budget.py`: context-managed exclusive authority,
   hash-pinned closed seed, append-only journal/anchors, global private storage checks,
   durable reservations and refusal after ambiguous interruption/corruption/reset.
   Test prior consumption, retries, zero remaining allowance, missing/truncated evidence,
   conflicting authorities and total retained-byte limits.
3. Optional hooks in `acquisition_session.py` and `private_storage.py`, targeted tests:
   preserve legacy defaults; bind reused requests/pages/timestamps to their original
   acquisitions; retain all action-scope evidence even on rejection; require the explicit
   gate before larger requests; apply aggregate quota checks before writes/publication.
4. `packages/data/requalification.py`, `requalification_cli.py`, new policy/config and
   synthetic tests: opt-in credential-free defaults, new immutable candidate/qualification
   identity, pinned old evidence/independent evidence, deterministic offline report and
   an explicit BLOCKED/RESTRICTED/READY decision. Test private output enforcement,
   contradictory/missing evidence, no false v2 admission and two-process replay.
5. Primary issuer evidence is private, bounded and hash-indexed. Preserve old workbooks,
   observations, receipts and negative comparisons. Verify exact dates/amount/currency/
   classification without silently choosing a convenient contradictory value.
6. After focused tests/static checks, run one finite pilot acquisition using only IEX.
   Stop before larger acquisition on any failed applicable gate. No historical strategy,
   optimization, AI result or empirical chart is authorized.
7. Full pytest/Ruff/established mypy/lock/Markdown checks, R3 workflow/recovery and old
   numerical projections; two offline qualifications per frozen candidate, including
   final checkout. Stage only code, synthetic tests and sanitized documentation; review
   every commit for private data. Commit/push non-force to main and verify synchronization.

## Review focus

- A pre-start ex-date can still create an inherited payable: exclusions require an
  explicit empty opening receivable state and independent starting cash.
- Provider-adjusted inputs or earlier warm-up can reintroduce action dependencies.
- Complete process-date pagination is not complete effective-date inventory.
- A fresh workspace cannot reset the original aggregate budget; interrupted reservations
  and storage across workspaces remain charged or fail closed.
- Scope selection cannot turn derived pages into original provider provenance, erase
  special flags, silently repair payable dates or weaken strict v2 admission.

Deliver `R4B1_IMPLEMENTATION.md`, `R4B1_DATA_QUALIFICATION.md`, `R4B1_VERIFICATION.md`.
Engineering correctness and dataset readiness are separate judgments. Independent
acceptance belongs to external review. Stop after R4-B.1.
