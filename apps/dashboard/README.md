# AI-Assisted Quant Research — Historical Dashboard Preview

This directory retains the v0.6 static dashboard preview for local historical reference.
Its milestone evidence, runtime labels and paper/Level 4 blockers describe that earlier scope.
The v0.7 research framework is in development; this scaffold is not a research-results viewer.
No frontend framework is installed. See the [current specification](../../docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md).

The historical dashboard contract covers read-only monitoring plus safe control-plane actions
routed through backend contracts. The static preview has no connected controls. It must not
contain broker credentials, AI provider credentials, order-entry forms,
natural-language trading inputs, direct broker calls, direct AI/news provider calls, or autonomous
execution workers.

The retained Milestone 25 dashboard/control-plane runtime smoke is implemented server-side in
`packages/control_plane/runtime.py` and `scripts/check_dashboard_control_plane_runtime.py`. It builds
fake/local read-only snapshots and validates safe controls through fake dispatch by default. It does
not deploy, activate schedules, send Telegram alerts, call broker APIs, call AI/news providers, or
send real Temporal control signals by default.

Allowed public environment names are defined in `public_env.py`.

Milestone 26 added `build-preview.mjs` and static preview files under `src/`. The preview displays
safe placeholder status only: dev/preview labels, disabled live trading, disabled autonomous
execution, paper-operation and Level 4 blockers, milestone smoke evidence, and pending evidence
gaps. It does not connect to backend services from the browser and does not deploy workers.
These operational milestones are historical records rather than v0.7 completion criteria.
Use this scaffold locally; v0.7 does not authorize deployment or broker-connected operation.
