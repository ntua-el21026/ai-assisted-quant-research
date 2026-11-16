"""Local research checkpoints with explicit SQLite transactions and integrity checks.

This ledger contains no broker state and does not import the historical managed
database package. SQLite commits are separate from filesystem publication.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from packages.research.artifacts import canonical_json

LedgerState = Literal["REGISTERED", "RUNNING", "PREPARED", "PUBLISHED", "COMMITTED", "FAILED"]


class ResearchConflict(ValueError):
    """A request or transition conflicts with an immutable experiment binding."""


class ResearchStateCorruption(ValueError):
    """Persisted state cannot be verified; evidence must be retained unchanged."""


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_sha(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe_relative(value: str) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "\x00" not in value
        and "\\" not in value
        and not PurePosixPath(value).is_absolute()
        and not {".", ".."}.intersection(value.split("/"))
        and str(PurePosixPath(value)) == value
    )


@dataclass(frozen=True)
class PreparedResult:
    run_id: str
    deterministic_sha256: str
    artifact_hashes: dict[str, str]
    stage_relpath: str
    output_relpath: str
    runtime_sha256: str

    def __post_init__(self) -> None:
        if (
            not _valid_sha(self.run_id)
            or not _valid_sha(self.deterministic_sha256)
            or not _valid_sha(self.runtime_sha256)
        ):
            raise ValueError("invalid_prepared_identity")
        if (
            not isinstance(self.artifact_hashes, dict)
            or "manifest.json" not in self.artifact_hashes
        ):
            raise ValueError("invalid_prepared_artifact_index")
        if any(
            not _safe_relative(name)
            or name in {"hashes.json", "runtime.json"}
            or not _valid_sha(sha)
            for name, sha in self.artifact_hashes.items()
        ):
            raise ValueError("invalid_prepared_artifact_index")
        if _digest(canonical_json(self.artifact_hashes)) != self.deterministic_sha256:
            raise ValueError("prepared_aggregate_mismatch")
        if (
            not _safe_relative(self.stage_relpath)
            or not _safe_relative(self.output_relpath)
            or self.stage_relpath == self.output_relpath
        ):
            raise ValueError("invalid_prepared_paths")
        # Do not retain a caller's mutable dictionary alias.
        object.__setattr__(self, "artifact_hashes", dict(sorted(self.artifact_hashes.items())))


@dataclass(frozen=True)
class LedgerRecord:
    experiment_id: str
    request_sha256: str
    request_json: str
    state: LedgerState
    attempt_count: int
    prepared: PreparedResult | None
    failure_reason: str | None


class ResearchLedger(Protocol):
    def register(
        self, experiment_id: str, request_sha256: str, request_json: str
    ) -> LedgerRecord: ...
    def get(self, experiment_id: str) -> LedgerRecord | None: ...
    def find_run(self, run_id: str) -> LedgerRecord | None: ...
    def start_attempt(self, experiment_id: str) -> LedgerRecord: ...
    def prepare(self, experiment_id: str, prepared: PreparedResult) -> LedgerRecord: ...
    def mark_published(self, experiment_id: str) -> LedgerRecord: ...
    def commit(self, experiment_id: str) -> LedgerRecord: ...
    def fail(self, experiment_id: str, reason: str) -> LedgerRecord: ...
    def events(self, experiment_id: str) -> tuple[dict[str, object], ...]: ...
    def counts(self, experiment_id: str) -> dict[str, int]: ...


_SCHEMA = (
    """CREATE TABLE research_experiments (
        experiment_id TEXT PRIMARY KEY NOT NULL,
        request_sha256 TEXT NOT NULL UNIQUE,
        request_json TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN
            ('REGISTERED','RUNNING','PREPARED','PUBLISHED','COMMITTED','FAILED')),
        attempt_count INTEGER NOT NULL DEFAULT 0
            CHECK (typeof(attempt_count)='integer' AND attempt_count >= 0),
        prepared_json TEXT,
        run_id TEXT UNIQUE,
        output_relpath TEXT UNIQUE,
        failure_reason TEXT
    )""",
    """CREATE TABLE research_events (
        experiment_id TEXT NOT NULL REFERENCES research_experiments(experiment_id),
        sequence INTEGER NOT NULL CHECK (typeof(sequence)='integer' AND sequence > 0),
        event_type TEXT NOT NULL CHECK (event_type IN
            ('registered','attempt_started','prepared','published','committed','failed')),
        details_json TEXT NOT NULL,
        previous_sha256 TEXT NOT NULL,
        event_sha256 TEXT NOT NULL,
        PRIMARY KEY (experiment_id, sequence)
    )""",
    """CREATE UNIQUE INDEX research_checkpoint_once
        ON research_events(experiment_id, event_type)
        WHERE event_type != 'attempt_started'""",
    """CREATE TABLE research_results (
        experiment_id TEXT PRIMARY KEY NOT NULL
            REFERENCES research_experiments(experiment_id),
        run_id TEXT NOT NULL UNIQUE,
        deterministic_sha256 TEXT NOT NULL,
        prepared_json TEXT NOT NULL
    )""",
)


def _normalize_sql(value: str) -> str:
    return " ".join(value.strip().rstrip(";").split())


def _validate_request(experiment_id: str, sha: str, raw: str) -> None:
    if (
        not isinstance(experiment_id, str)
        or not experiment_id
        or experiment_id != experiment_id.strip()
    ):
        raise ValueError("invalid_experiment_id")
    if not _valid_sha(sha) or not isinstance(raw, str) or _digest(raw.encode()) != sha:
        raise ValueError("invalid_request_fingerprint")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or canonical_json(value).decode() != raw:
            raise ValueError("request_must_be_canonical_json_object")
    except (TypeError, ValueError) as exc:
        raise ValueError("request_must_be_canonical_json_object") from exc


def _prepared_json(prepared: PreparedResult) -> str:
    return canonical_json(asdict(prepared)).decode()


def _load_prepared(raw: str) -> PreparedResult:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid_prepared_json")
    result = PreparedResult(**value)
    if _prepared_json(result) != raw:
        raise ValueError("noncanonical_prepared_json")
    return result


def _database_error(exc: sqlite3.DatabaseError) -> None:
    primary = getattr(exc, "sqlite_errorcode", 0) & 255
    if primary in {
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
        sqlite3.SQLITE_IOERR,
        sqlite3.SQLITE_FULL,
        sqlite3.SQLITE_CANTOPEN,
        sqlite3.SQLITE_READONLY,
    }:
        raise exc
    raise ResearchStateCorruption("sqlite_state_unverifiable") from exc


class SQLiteResearchLedger:
    """A separate local database; each operation closes its own connection.

    Audit sequence/hash chains detect accidental loss or contradictory edits;
    they are not signatures against a coordinated malicious database rewrite.
    SQLite busy/I/O/full/read-only errors remain explicit retry-policy inputs.
    """

    def __init__(self, path: Path) -> None:
        path = path.absolute()
        self.path = path
        existed = path.exists()
        if path.is_symlink():
            raise ResearchStateCorruption("ledger_symlink_forbidden")
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection(create=not existed) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                objects = connection.execute(
                    "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
                ).fetchall()
                if not objects:
                    if existed:
                        raise ResearchStateCorruption("uninitialized_existing_ledger")
                    for statement in _SCHEMA:
                        connection.execute(statement)
                    connection.execute("PRAGMA user_version=1")
                self._validate_database(connection)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextmanager
    def _connection(self, *, create: bool = False) -> Iterator[sqlite3.Connection]:
        connection: sqlite3.Connection | None = None
        try:
            if self.path.is_symlink():
                raise ResearchStateCorruption("ledger_symlink_forbidden")
            if not create and not self.path.is_file():
                raise ResearchStateCorruption("ledger_missing_or_not_file")
            connection = sqlite3.connect(
                self.path.as_uri() + ("?mode=rwc" if create else "?mode=rw"),
                uri=True,
                timeout=5,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        except sqlite3.DatabaseError as exc:
            _database_error(exc)
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def _transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                self._validate_database(connection)
                yield connection
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ResearchConflict("research_uniqueness_conflict") from exc
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _validate_database(connection: sqlite3.Connection) -> None:
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ResearchStateCorruption("unsupported_research_ledger_version")
        actual = {
            _normalize_sql(str(row["sql"]))
            for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        if actual != {_normalize_sql(sql) for sql in _SCHEMA}:
            raise ResearchStateCorruption("research_ledger_schema_mismatch")
        if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ResearchStateCorruption("research_ledger_integrity_failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ResearchStateCorruption("research_ledger_foreign_key_failed")

    def _read(self, connection: sqlite3.Connection, experiment_id: str) -> LedgerRecord | None:
        row = connection.execute(
            "SELECT * FROM research_experiments WHERE experiment_id=?", (experiment_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            _validate_request(row["experiment_id"], row["request_sha256"], row["request_json"])
            prepared = _load_prepared(row["prepared_json"]) if row["prepared_json"] else None
            if (row["run_id"], row["output_relpath"]) != (
                prepared.run_id if prepared else None,
                prepared.output_relpath if prepared else None,
            ):
                raise ValueError("prepared_columns_disagree")
            self._verify_events(connection, row, prepared)
            result = connection.execute(
                "SELECT * FROM research_results WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
            if row["state"] == "COMMITTED":
                if (
                    result is None
                    or prepared is None
                    or (result["run_id"], result["deterministic_sha256"], result["prepared_json"])
                    != (prepared.run_id, prepared.deterministic_sha256, _prepared_json(prepared))
                ):
                    raise ValueError("committed_result_disagrees")
            elif result is not None:
                raise ValueError("result_before_commit")
            return LedgerRecord(
                experiment_id=row["experiment_id"],
                request_sha256=row["request_sha256"],
                request_json=row["request_json"],
                state=row["state"],
                attempt_count=row["attempt_count"],
                prepared=prepared,
                failure_reason=row["failure_reason"],
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise ResearchStateCorruption("research_record_unverifiable") from exc

    @staticmethod
    def _verify_events(
        connection: sqlite3.Connection, row: sqlite3.Row, prepared: PreparedResult | None
    ) -> None:
        previous = "0" * 64
        state: str | None = None
        attempts = 0
        evidence: PreparedResult | None = None
        failure: str | None = None
        events = connection.execute(
            "SELECT * FROM research_events WHERE experiment_id=? ORDER BY sequence",
            (row["experiment_id"],),
        ).fetchall()
        for sequence, event in enumerate(events, start=1):
            details = json.loads(event["details_json"])
            expected_hash = _digest(
                canonical_json(
                    {
                        "experiment_id": row["experiment_id"],
                        "sequence": sequence,
                        "event_type": event["event_type"],
                        "details": details,
                        "previous_sha256": previous,
                    }
                )
            )
            if (event["sequence"], event["previous_sha256"], event["event_sha256"]) != (
                sequence,
                previous,
                expected_hash,
            ) or canonical_json(details).decode() != event["details_json"]:
                raise ValueError("event_chain_mismatch")
            kind = event["event_type"]
            if (
                kind == "registered"
                and state is None
                and details
                == {"request_sha256": row["request_sha256"], "request_json": row["request_json"]}
            ):
                state = "REGISTERED"
            elif (
                kind == "attempt_started"
                and state in {"REGISTERED", "RUNNING"}
                and (details == {"attempt": attempts + 1})
            ):
                attempts += 1
                state = "RUNNING"
            elif kind == "prepared" and state == "RUNNING":
                evidence = _load_prepared(event["details_json"])
                state = "PREPARED"
            elif (
                kind == "published"
                and state == "PREPARED"
                and evidence
                and (details == {"run_id": evidence.run_id})
            ):
                state = "PUBLISHED"
            elif (
                kind == "committed"
                and state == "PUBLISHED"
                and evidence
                and details
                == {
                    "run_id": evidence.run_id,
                    "deterministic_sha256": evidence.deterministic_sha256,
                }
            ):
                state = "COMMITTED"
            elif (
                kind == "failed"
                and state in {"REGISTERED", "RUNNING", "PREPARED", "PUBLISHED"}
                and isinstance(details, dict)
                and set(details) == {"reason"}
                and isinstance(details["reason"], str)
                and details["reason"]
            ):
                state, failure = "FAILED", details["reason"]
            else:
                raise ValueError("illegal_event_transition")
            previous = expected_hash
        if (state, attempts, evidence, failure) != (
            row["state"],
            row["attempt_count"],
            prepared,
            row["failure_reason"],
        ):
            raise ValueError("event_state_disagrees")

    @staticmethod
    def _append(
        connection: sqlite3.Connection, experiment_id: str, kind: str, details: Any
    ) -> None:
        prior = connection.execute(
            "SELECT sequence,event_sha256 FROM research_events WHERE experiment_id=? "
            "ORDER BY sequence DESC LIMIT 1",
            (experiment_id,),
        ).fetchone()
        sequence = prior["sequence"] + 1 if prior else 1
        previous = prior["event_sha256"] if prior else "0" * 64
        digest = _digest(
            canonical_json(
                {
                    "experiment_id": experiment_id,
                    "sequence": sequence,
                    "event_type": kind,
                    "details": details,
                    "previous_sha256": previous,
                }
            )
        )
        connection.execute(
            "INSERT INTO research_events VALUES (?,?,?,?,?,?)",
            (experiment_id, sequence, kind, canonical_json(details).decode(), previous, digest),
        )

    def _required(self, connection: sqlite3.Connection, experiment_id: str) -> LedgerRecord:
        record = self._read(connection, experiment_id)
        if record is None:
            raise ResearchConflict("unknown_research_experiment")
        return record

    def register(self, experiment_id: str, request_sha256: str, request_json: str) -> LedgerRecord:
        _validate_request(experiment_id, request_sha256, request_json)
        with self._transaction(write=True) as connection:
            record = self._read(connection, experiment_id)
            if record is not None:
                if (record.request_sha256, record.request_json) != (request_sha256, request_json):
                    raise ResearchConflict("experiment_request_conflict")
                return record
            connection.execute(
                "INSERT INTO research_experiments "
                "(experiment_id,request_sha256,request_json,state) VALUES (?,?,?,'REGISTERED')",
                (experiment_id, request_sha256, request_json),
            )
            self._append(
                connection,
                experiment_id,
                "registered",
                {
                    "request_sha256": request_sha256,
                    "request_json": request_json,
                },
            )
            return self._required(connection, experiment_id)

    def get(self, experiment_id: str) -> LedgerRecord | None:
        with self._transaction() as connection:
            return self._read(connection, experiment_id)

    def find_run(self, run_id: str) -> LedgerRecord | None:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT experiment_id FROM research_experiments WHERE run_id=?", (run_id,)
            ).fetchone()
            return self._read(connection, row[0]) if row is not None else None

    def start_attempt(self, experiment_id: str) -> LedgerRecord:
        with self._transaction(write=True) as connection:
            record = self._required(connection, experiment_id)
            if record.state not in {"REGISTERED", "RUNNING"}:
                raise ResearchConflict("attempt_not_allowed")
            connection.execute(
                "UPDATE research_experiments SET state='RUNNING',attempt_count=attempt_count+1 "
                "WHERE experiment_id=?",
                (experiment_id,),
            )
            self._append(
                connection,
                experiment_id,
                "attempt_started",
                {
                    "attempt": record.attempt_count + 1,
                },
            )
            return self._required(connection, experiment_id)

    def prepare(self, experiment_id: str, prepared: PreparedResult) -> LedgerRecord:
        # Validate again even if a caller mutated the dataclass's dictionary member.
        prepared = PreparedResult(**asdict(prepared))
        with self._transaction(write=True) as connection:
            record = self._required(connection, experiment_id)
            if (
                record.state in {"PREPARED", "PUBLISHED", "COMMITTED"}
                and record.prepared == prepared
            ):
                return record
            if record.state != "RUNNING":
                raise ResearchConflict("prepare_not_allowed_or_conflicting")
            connection.execute(
                "UPDATE research_experiments SET state='PREPARED',prepared_json=?,run_id=?,"
                "output_relpath=? WHERE experiment_id=?",
                (_prepared_json(prepared), prepared.run_id, prepared.output_relpath, experiment_id),
            )
            self._append(connection, experiment_id, "prepared", asdict(prepared))
            return self._required(connection, experiment_id)

    def mark_published(self, experiment_id: str) -> LedgerRecord:
        with self._transaction(write=True) as connection:
            record = self._required(connection, experiment_id)
            if record.state in {"PUBLISHED", "COMMITTED"}:
                return record
            if record.state != "PREPARED" or record.prepared is None:
                raise ResearchConflict("publish_not_allowed")
            connection.execute(
                "UPDATE research_experiments SET state='PUBLISHED' WHERE experiment_id=?",
                (experiment_id,),
            )
            self._append(connection, experiment_id, "published", {"run_id": record.prepared.run_id})
            return self._required(connection, experiment_id)

    def commit(self, experiment_id: str) -> LedgerRecord:
        with self._transaction(write=True) as connection:
            record = self._required(connection, experiment_id)
            if record.state == "COMMITTED":
                return record
            if record.state != "PUBLISHED" or record.prepared is None:
                raise ResearchConflict("commit_not_allowed")
            p = record.prepared
            connection.execute(
                "INSERT INTO research_results VALUES (?,?,?,?)",
                (experiment_id, p.run_id, p.deterministic_sha256, _prepared_json(p)),
            )
            connection.execute(
                "UPDATE research_experiments SET state='COMMITTED' WHERE experiment_id=?",
                (experiment_id,),
            )
            self._append(
                connection,
                experiment_id,
                "committed",
                {
                    "run_id": p.run_id,
                    "deterministic_sha256": p.deterministic_sha256,
                },
            )
            return self._required(connection, experiment_id)

    def fail(self, experiment_id: str, reason: str) -> LedgerRecord:
        if not isinstance(reason, str) or not reason:
            raise ValueError("failure_reason_required")
        with self._transaction(write=True) as connection:
            record = self._required(connection, experiment_id)
            if record.state == "FAILED" and record.failure_reason == reason:
                return record
            if record.state in {"COMMITTED", "FAILED"}:
                raise ResearchConflict("terminal_state_cannot_be_reclassified")
            connection.execute(
                "UPDATE research_experiments SET state='FAILED',failure_reason=? "
                "WHERE experiment_id=?",
                (reason, experiment_id),
            )
            self._append(connection, experiment_id, "failed", {"reason": reason})
            return self._required(connection, experiment_id)

    def events(self, experiment_id: str) -> tuple[dict[str, object], ...]:
        with self._transaction() as connection:
            self._read(connection, experiment_id)
            return tuple(
                {
                    "sequence": row["sequence"],
                    "event_type": row["event_type"],
                    "details": json.loads(row["details_json"]),
                    "previous_sha256": row["previous_sha256"],
                    "event_sha256": row["event_sha256"],
                }
                for row in connection.execute(
                    "SELECT * FROM research_events WHERE experiment_id=? ORDER BY sequence",
                    (experiment_id,),
                )
            )

    def counts(self, experiment_id: str) -> dict[str, int]:
        with self._transaction() as connection:
            record = self._read(connection, experiment_id)
            counts = {
                row["event_type"]: row["count"]
                for row in connection.execute(
                    "SELECT event_type,COUNT(*) AS count FROM research_events "
                    "WHERE experiment_id=? GROUP BY event_type",
                    (experiment_id,),
                )
            }
            return {
                "experiments": int(record is not None),
                "attempts": record.attempt_count if record else 0,
                "prepared_events": counts.get("prepared", 0),
                "published_events": counts.get("published", 0),
                "completion_events": counts.get("committed", 0),
                "committed_results": connection.execute(
                    "SELECT COUNT(*) FROM research_results WHERE experiment_id=?", (experiment_id,)
                ).fetchone()[0],
            }
