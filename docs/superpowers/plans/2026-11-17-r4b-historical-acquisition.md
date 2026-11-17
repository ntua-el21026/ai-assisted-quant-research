# R4-B historical acquisition and qualification plan

The owner separately authorizes this checkpoint after independent acceptance of
R4-A at `0dd0875c9f4a1ff806a107badcd693922d9f7e29`. Initial main, origin/main,
remote main and GitHub main match that clean SHA. Work remains on main, without
history rewriting. R4-C, strategy execution/optimization and empirical publication
are not authorized.

## Predeclared acquisition scope

All authenticated traffic uses the free paper-only account, explicit **IEX** raw
daily bars, and the documented corporate-actions data endpoint. The general SIP
FAQ and paper-only entitlement wording conflict. Support #397685 is owner-reported
authority for private noncommercial research/backtesting and local storage within
entitlements; it does not authorize historical SIP or public empirical outputs.
The new CLI refuses SIP for this checkpoint before loading credentials or networking.
The existing library's SIP interface remains available and unchanged for its tests.

Before viewing observations, the registered sequence is:

1. Narrow bar preflight: SPY/QQQ, 2025-01-06 through 2025-01-10. The official
   calendar excludes January 9 (Carter closure); four sessions per symbol are expected.
   Query action response shape separately with all types/data-quality records.
2. Pilot: SPY/QQQ raw IEX, civil dates 2024-01-01 through 2025-12-31. Official
   core calendar has 502 sessions, six early closes and 1004 expected observations.
   This exercises daily DST, closures and actual global multi-symbol pagination.
3. Only if the pilot's raw-price completeness/schema checks pass, acquire the small
   two-ETF candidate from 2020-01-01 through 2025-12-31: 1508 sessions/3016 expected
   pairs before exclusions. This assesses a portion of rolling development and the
   proposed final segment without measuring trading returns. No 2012–2015 or full
   design-period availability is implied.
4. Bounded diagnostic weeks in 2016–2019 assess returned coverage without pretending
   to qualify full early-year calendars or corporate-action inventories. Preserve
   this period as restricted. Inventory all observed corporate-action categories
   using process windows that extend beyond ex-date coverage.
5. Small declared raw/adjusted split/dividend diagnostics examine known AAPL 4:1,
   NVDA 10:1 and ETF distribution boundaries. These are data-convention checks,
   never additions to the research universe or executable strategy inputs.

The machine-readable plan records exact requests, dates, types and resource limits.
No provider observation, cash rate, performance statistic or private receipt enters it.

## Boundaries and implementation

- Extend request/receipt feed types with explicit IEX while preserving SIP. Add an
  explicit corporate-action quality selector, defaulting to the accepted `complete`.
- Add a shared sequential budget around every actual GET, including retries: at
  most 100 reservations, 250 MiB of application-read payload across all statuses
  (stronger than the success-only cap), 16 MiB/response, 900 seconds and at least
  .35 seconds between GETs. A process watchdog bounds the actual CLI invocation.
  HTTP headers/TLS/kernel buffering are outside the payload-byte counter.
- Durably record reservations/body counts/status before continuing. Interrupted
  network workspaces are retained and never automatically reset or resumed.
- Credentials are parsed only by explicit acquisition from the caller's local file;
  never echo values, dump environment, trace shell, follow redirects or use proxies.
- Use fresh gitignored private workspaces with 0700 directories/0600 files. Preserve
  raw successful bodies before normalization, including partial/unsupported evidence.
  Cap retained files, copies and generated reports at 1 GiB before writing.
- Keep a separate `historical-candidate/v1` evidence envelope. It can truthfully retain
  incomplete/unqualified inputs without weakening `market-snapshot/v2`. Reuse exact
  normalization, v2 observations/provenance, existing hashes and atomic publication.
- Produce deterministic price-free quality reports, per-feed/role coverage, action
  inventory/reconciliation, identity/availability/rights classifications and strict
  v2 admission diagnostics. Runtime/host metadata is separate. Offline replay never
  needs credentials or provider access.
- Existing strategy, risk, simulator, metrics, R3 ledger/workflow and synthetic examples
  remain untouched. No candidate is automatically promoted to a historical experiment.

## Test-first work packages

1. Explicit feed/quality extensions and budgeted transport: mocked GET success/errors,
   exact query binding, all retries/pages, byte/deadline/rate and durable-callback failures.
2. Official source-backed calendar: annual literal counts, Carter/Juneteenth exceptions,
   DST/early close offsets, malformed/ambiguous provenance and pinned hash failures.
3. Candidate envelope and quality report: frozen inventory/hash safety, partial queries,
   impossible pagination, duplicates/missing bars, unsupported actions, uncertain identities,
   rights/availability, incompatible feeds and deterministic sanitized reports.
4. Opt-in CLI and private storage: no-network defaults, credential secrecy, IEX entitlement
   refusal, bounded stage gating, immutable files, gitignore/permissions and no publication
   outside the private root. Use synthetic transports for every implementation test.
5. Execute the registered actual preflight/pilot/conditional candidate once after focused
   tests pass. Preserve failures. Independently reconcile issuer evidence privately where
   available; never infer inventory completeness from a successful API response.
6. Full tests/static/lock/docs checks, old numerical projections, two final-checkout offline
   qualification replays, internal review, sanitized reports, coherent commits and non-force
   push with fresh canonical synchronization checks. Stop after R4-B.

The expected engineering deliverable is distinct from dataset readiness. A tested pipeline
can pass engineering while the candidate remains restricted or blocked for R4-C because
coverage, corporate actions, historical availability or rights cannot be established.
