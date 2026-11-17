"""Optional finite local acquisition. All ordinary research commands remain offline."""

from __future__ import annotations

import argparse
import signal
from pathlib import Path

from packages.data.acquisition_plan import load_acquisition_plan, load_alpaca_credentials
from packages.data.acquisition_session import acquire_registered_candidate, qualify_candidate
from packages.data.alpaca_historical import UrllibHistoricalTransport
from packages.research.artifacts import canonical_json


class _Deadline(BaseException):
    pass


def _deadline(signum: int, frame: object) -> None:
    raise _Deadline()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Offline authorization/calendar/budget validation")
    plan.add_argument("--plan", type=Path, required=True)
    acquisition = commands.add_parser("acquire", help="Explicit private read-only IEX acquisition")
    acquisition.add_argument("--plan", type=Path, required=True)
    acquisition.add_argument("--workspace", type=Path, required=True)
    acquisition.add_argument("--credentials-file", type=Path, required=True)
    acquisition.add_argument("--allow-network", action="store_true")
    qualification = commands.add_parser("qualify", help="Offline frozen-candidate qualification")
    qualification.add_argument("--candidate", type=Path, required=True)
    qualification.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "acquire" and not args.allow_network:
        print('{"error":"explicit_network_authorization_required"}')
        return 2
    try:
        if args.command == "qualify":
            result = qualify_candidate(args.candidate, args.output)
        else:
            registered = load_acquisition_plan(args.plan)
            if args.command == "plan":
                result = {
                    "plan_sha256": registered.sha256,
                    "feed": registered.plan.feed,
                    "request_groups": len(registered.plan.stages),
                    "budget": registered.plan.budget.model_dump(mode="json"),
                    "network": False,
                }
            else:
                # Verify path/ignore policy before any authenticated request. Credentials
                # are parsed only by this branch, never discovered from the environment.
                repository = Path(__file__).resolve().parents[2]
                credentials = load_alpaca_credentials(args.credentials_file)
                print('{"credentials_available":true}', flush=True)
                transport = UrllibHistoricalTransport(credentials.api_key, credentials.secret_key)
                previous = signal.signal(signal.SIGALRM, _deadline)
                signal.setitimer(signal.ITIMER_REAL, registered.plan.budget.max_elapsed_seconds)
                try:
                    acquired = acquire_registered_candidate(
                        registered,
                        repository=repository,
                        workspace=args.workspace,
                        transport=transport,
                        kind="historical",
                    )
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previous)
                result = {
                    "manifest_path": str(acquired.manifest_path),
                    "attempts": acquired.attempts,
                    "received_body_bytes": acquired.received_body_bytes,
                    "successful_body_bytes": acquired.successful_body_bytes,
                    "pilot_passed": acquired.pilot_passed,
                    "stopped_code": acquired.stopped_code,
                }
        print(canonical_json(result).decode(), end="")
        if args.command == "acquire" and acquired.stopped_code is not None:
            return 1
        return 0
    except _Deadline:
        print('{"error":"session_deadline_exceeded","manual_budget_review_required":true}')
        return 1
    except Exception as exc:
        # No provider/validation/file contents, credentials, URL/header dumps or
        # exception repr. Approved codes carry only lower-case identifiers.
        code = getattr(exc, "code", None)
        safe = (
            code
            if isinstance(code, str) and code.replace("_", "").isalnum()
            else "acquisition_failed"
        )
        if isinstance(exc, ValueError) and str(exc) == "credentials_unavailable":
            print('{"credentials_available":false}')
            safe = "credentials_unavailable"
        print(canonical_json({"error": safe}).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
