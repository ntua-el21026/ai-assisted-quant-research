"""Single-host aggregate acquisition authority; prior evidence is never rewritten.

Every reservation is journaled and independently anchored before GET. Outstanding
attempts or damaged state require manual audit. A new process never refunds or
resumes an interrupted attempt. Filesystem metadata and hostile coordinated edits
are outside the declared sequential cooperative execution contract.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from packages.data.acquisition_budget import HistoricalSessionBudget

MAX_ATTEMPTS = 100
MAX_BODY_BYTES = 250 * 1024 * 1024
MAX_LOCAL_BYTES = 1024**3


class CheckpointBudgetError(RuntimeError):
    """Closed codes exclude filesystem paths and source content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BudgetReceiptReference:
    path: Path
    sha256: str
    size_bytes: int


def _wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _decode(raw: bytes) -> Any:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject)


def _safe(path: Path) -> None:
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise CheckpointBudgetError("checkpoint_budget_path")


def _read(path: Path, limit: int = 16 * 1024 * 1024) -> bytes:
    _safe(path)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError
    return data


@dataclass
class _Counters:
    attempts: int = 0
    received: int = 0
    successful: int = 0
    active: bool = False
    allowance: int = 0
    attempt_bytes: int = 0

    def advance(self, event: Mapping[str, object]) -> None:
        def integer(name: str) -> int:
            value = event[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError
            return value

        kind = event["event"]
        attempts = self.attempts
        received, successful = self.received, self.successful
        if kind == "attempt_reserved":
            if self.active or self.attempts >= MAX_ATTEMPTS:
                raise ValueError
            allowance = integer("request_body_budget")
            if not 1 <= allowance <= min(16 * 1024 * 1024, MAX_BODY_BYTES - received):
                raise ValueError
            if event["endpoint_path"] not in {"/v2/stocks/bars", "/v1/corporate-actions"}:
                raise ValueError
            if re.fullmatch(r"[0-9a-f]{64}", str(event["query_sha256"])) is None:
                raise ValueError
            attempts += 1
            self.active, self.allowance, self.attempt_bytes = True, allowance, 0
        elif kind == "body_received":
            count = integer("chunk_bytes")
            if not self.active or not 1 <= count <= self.allowance - self.attempt_bytes:
                raise ValueError
            self.attempt_bytes += count
            received += count
            if event["status_code"] == 200:
                successful += count
        elif kind == "attempt_finished":
            if not self.active:
                raise ValueError
            self.active = False
        else:
            raise ValueError
        if (
            integer("attempt_id") != attempts
            or integer("attempts") != attempts
            or integer("received_body_bytes") != received
            or integer("successful_body_bytes") != successful
            or not 0 <= successful <= received <= MAX_BODY_BYTES
        ):
            raise ValueError
        self.attempts, self.received, self.successful = attempts, received, successful


class CheckpointBudgetAuthority:
    """Append-only aggregate authority for explicit successive fresh workspaces.

    The original closed R4-B receipt must contain exactly two attempts and 1,457
    received HTTP-200 body bytes. Reopening verifies the original seed and every
    event/anchor. Only one budget may be created per locked authority context.
    Deadlines remain finite per authorized session; request/body/storage ceilings
    aggregate across sessions. No automatic interrupted-session continuation exists.
    """

    def __init__(
        self,
        authority_dir: Path,
        repository: Path,
        seed_events_path: Path,
        expected_seed_sha256: str,
        prior_receipts: Sequence[BudgetReceiptReference] = (),
    ) -> None:
        self.directory = authority_dir.absolute()
        self.repository = repository.absolute()
        self.base = self.repository / "datasets/private/r4b"
        self.seed_path = seed_events_path.absolute()
        self.seed_sha256 = expected_seed_sha256
        self.prior_receipts = tuple(prior_receipts)
        self._fd: int | None = None
        self._entered = False
        self._created_budget = False
        self._failed = False
        self._sequence = 0
        self._head = ""
        self._counts = _Counters()

    def __enter__(self) -> Self:
        if self._entered or self._fd is not None:
            raise CheckpointBudgetError("checkpoint_budget_busy")
        try:
            for path in (self.directory, self.repository, self.base, self.seed_path):
                _safe(path)
            if (
                not self.directory.is_relative_to(self.base)
                or self.directory == self.base
                or not self.seed_path.is_relative_to(self.base)
                or self.seed_path.is_relative_to(self.directory)
            ):
                raise CheckpointBudgetError("checkpoint_budget_path")
            ignored = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repository),
                    "check-ignore",
                    "--quiet",
                    "--no-index",
                    "--",
                    self.directory.relative_to(self.repository).as_posix() + "/",
                ],
                capture_output=True,
                check=False,
                timeout=10,
            )
            if ignored.returncode:
                raise CheckpointBudgetError("checkpoint_budget_path")
            header = self._seed_header()
            fresh = not self.directory.exists()
            pointer = self.base / ".checkpoint-budget-authority.json"
            binding = (
                _wire(
                    {
                        "authority_dir": self.directory.relative_to(self.base).as_posix(),
                        "seed_sha256": self.seed_sha256,
                    }
                )
                + b"\n"
            )
            pointer_exists = pointer.exists()
            if pointer_exists and (fresh or _read(pointer) != binding):
                raise CheckpointBudgetError("checkpoint_budget_journal")
            if not pointer_exists and not fresh:
                raise CheckpointBudgetError("checkpoint_budget_journal")
            if fresh:
                self.directory.mkdir(mode=0o700)
                self.directory.chmod(0o700)
            lock = self.directory / "authority.lock"
            self._fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CheckpointBudgetError("checkpoint_budget_busy") from None
            self._entered = True
            if fresh:
                self._write_new(pointer, binding)
                self._write_new(self.directory / "seed.json", _wire(header) + b"\n")
                (self.directory / "anchors").mkdir(mode=0o700)
                self._write_new(self.directory / "events.jsonl", b"")
            elif _read(self.directory / "seed.json") != _wire(header) + b"\n":
                raise CheckpointBudgetError("checkpoint_budget_seed")
            self._counts = _Counters(2, 1457, 1457)
            self._head = hashlib.sha256(_wire(header)).hexdigest()
            self._replay()
            if self._counts.active:
                raise CheckpointBudgetError("checkpoint_budget_inflight")
            self.check_storage()
            return self
        except BaseException as exc:
            self._release()
            if isinstance(exc, CheckpointBudgetError | KeyboardInterrupt | SystemExit):
                raise
            raise CheckpointBudgetError("checkpoint_budget_journal") from None

    def __exit__(self, *args: object) -> None:
        self._release()

    def _release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._entered = False

    def _seed_header(self) -> dict[str, object]:
        try:
            raw = _read(self.seed_path)
            if hashlib.sha256(raw).hexdigest() != self.seed_sha256 or not raw.endswith(b"\n"):
                raise ValueError
            counts = _Counters()
            for line in raw.splitlines():
                event = _decode(line)
                if not isinstance(event, dict):
                    raise ValueError
                counts.advance(event)
            if counts.active or (counts.attempts, counts.received, counts.successful) != (
                2,
                1457,
                1457,
            ):
                raise ValueError
            references = []
            for reference in self.prior_receipts:
                path = reference.path.absolute()
                if not path.is_relative_to(self.base):
                    raise ValueError
                body = _read(path)
                if (
                    len(body) != reference.size_bytes
                    or hashlib.sha256(body).hexdigest() != reference.sha256
                ):
                    raise ValueError
                references.append(
                    {
                        "path": path.relative_to(self.repository).as_posix(),
                        "sha256": reference.sha256,
                        "size_bytes": reference.size_bytes,
                    }
                )
            return {
                "schema_version": "checkpoint-budget/v1",
                "checkpoint": "R4-B",
                "seed_path": self.seed_path.relative_to(self.repository).as_posix(),
                "seed_sha256": self.seed_sha256,
                "seed_size_bytes": len(raw),
                "initial_attempts": 2,
                "initial_received_body_bytes": 1457,
                "initial_successful_body_bytes": 1457,
                "prior_receipts": references,
            }
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            raise CheckpointBudgetError("checkpoint_budget_seed") from None

    def _write_new(self, path: Path, body: bytes) -> None:
        self.check_storage(len(body))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        self._sync(path.parent)

    @staticmethod
    def _sync(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _replay(self) -> None:
        journal = _read(self.directory / "events.jsonl")
        if journal and not journal.endswith(b"\n"):
            raise ValueError
        for line in journal.splitlines():
            record = _decode(line)
            if not isinstance(record, dict):
                raise ValueError
            digest = record.pop("sha256")
            if (
                record["sequence"] != self._sequence + 1
                or record["previous_sha256"] != self._head
                or hashlib.sha256(_wire(record)).hexdigest() != digest
            ):
                raise ValueError
            expected = _wire({"sequence": record["sequence"], "sha256": digest}) + b"\n"
            if _read(self.directory / "anchors" / f"{record['sequence']:08d}.json") != expected:
                raise ValueError
            self._counts.advance(record["event"])
            self._sequence += 1
            self._head = digest
        anchors = {p.name for p in (self.directory / "anchors").iterdir()}
        if anchors != {f"{number:08d}.json" for number in range(1, self._sequence + 1)}:
            raise ValueError
        if {p.name for p in self.directory.iterdir()} != {
            "seed.json",
            "authority.lock",
            "anchors",
            "events.jsonl",
        }:
            raise ValueError

    def check_storage(self, additional_bytes: int = 0) -> None:
        """Count every retained regular file across the complete private R4-B root."""
        if not self._entered or self._failed:
            raise CheckpointBudgetError("checkpoint_budget_journal")
        if (
            isinstance(additional_bytes, bool)
            or not isinstance(additional_bytes, int)
            or additional_bytes < 0
        ):
            raise CheckpointBudgetError("checkpoint_budget_storage_limit")
        total = 0
        try:
            _safe(self.base)
            for parent, directories, files in os.walk(self.base, onerror=self._walk_error):
                for name in (*directories, *files):
                    details = (Path(parent) / name).lstat()
                    if stat.S_ISREG(details.st_mode):
                        total += details.st_size
                    elif not stat.S_ISDIR(details.st_mode):
                        raise CheckpointBudgetError("checkpoint_budget_path")
            if total + additional_bytes > MAX_LOCAL_BYTES:
                raise CheckpointBudgetError("checkpoint_budget_storage_limit")
        except OSError:
            raise CheckpointBudgetError("checkpoint_budget_storage_limit") from None

    @staticmethod
    def _walk_error(error: OSError) -> None:
        raise error

    def _record(self, event: Mapping[str, object]) -> None:
        if not self._entered or self._failed:
            raise CheckpointBudgetError("checkpoint_budget_journal")
        try:
            self._counts.advance(event)
            record = {
                "sequence": self._sequence + 1,
                "previous_sha256": self._head,
                "event": dict(event),
            }
            digest = hashlib.sha256(_wire(record)).hexdigest()
            body = _wire(record | {"sha256": digest}) + b"\n"
            anchor = _wire({"sequence": self._sequence + 1, "sha256": digest}) + b"\n"
            self.check_storage(len(body) + len(anchor))
            fd = os.open(self.directory / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            with os.fdopen(fd, "ab") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            self._write_new(self.directory / "anchors" / f"{self._sequence + 1:08d}.json", anchor)
            self._sequence += 1
            self._head = digest
        except Exception:
            self._failed = True
            raise CheckpointBudgetError("checkpoint_budget_journal") from None

    def session_budget(
        self,
        *,
        max_attempts: int = MAX_ATTEMPTS,
        max_received_body_bytes: int = MAX_BODY_BYTES,
        max_elapsed_seconds: float = 900,
        min_interval_seconds: float = 0.35,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        event_callback: Callable[[Mapping[str, object]], None] = lambda _: None,
    ) -> HistoricalSessionBudget:
        if not self._entered or self._failed:
            raise CheckpointBudgetError("checkpoint_budget_journal")
        if self._created_budget:
            raise CheckpointBudgetError("checkpoint_budget_session_exists")

        def observe(event: Mapping[str, object]) -> None:
            self._record(event)
            event_callback(event)

        budget = HistoricalSessionBudget(
            max_attempts=max_attempts,
            max_received_body_bytes=max_received_body_bytes,
            max_elapsed_seconds=max_elapsed_seconds,
            min_interval_seconds=min_interval_seconds,
            monotonic=monotonic,
            sleep=sleep,
            event_callback=observe,
            initial_attempts=self._counts.attempts,
            initial_received_body_bytes=self._counts.received,
            initial_successful_body_bytes=self._counts.successful,
        )
        self._created_budget = True
        return budget

    def snapshot(self) -> dict[str, object]:
        return {
            "attempts": self._counts.attempts,
            "received_body_bytes": self._counts.received,
            "successful_body_bytes": self._counts.successful,
            "inflight": self._counts.active,
            "sequence": self._sequence,
            "head_sha256": self._head,
            "seed_sha256": self.seed_sha256,
        }
