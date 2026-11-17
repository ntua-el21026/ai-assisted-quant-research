"""Publish private candidate evidence inside an immutable indexed envelope.

The strict candidate loader sees only evidence/; envelope hashes and runtime stay
outside that subtree. Raw provider and error bodies remain private inputs and are
never routed to a public artifact writer by this interface.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from packages.data.historical_candidates import CandidateManifest
from packages.data.private_storage import PrivateStorage
from packages.research.artifacts import canonical_json

PublicationCode = Literal[
    "candidate_private_storage_required",
    "candidate_publication_manifest",
    "candidate_publication_inventory",
    "candidate_publication_bytes",
    "candidate_publication_size",
    "candidate_publication_hash",
    "candidate_publication_path",
]


class CandidatePublicationError(ValueError):
    """Closed codes exclude source payloads, private references and output paths."""

    def __init__(self, code: PublicationCode) -> None:
        super().__init__(code)
        self.code = code


def publish_candidate(
    storage: PrivateStorage,
    relative: str,
    manifest: CandidateManifest,
    files: Mapping[str, bytes],
    runtime: bytes,
) -> Path:
    """Validate every declared byte before one private atomic publication.

    Existing destinations remain immutable. Storage accounts for the candidate,
    manifest, envelope index and runtime before creating publication staging.
    Source-content defects belong to offline qualification, not this byte check.
    """
    if not isinstance(storage, PrivateStorage):
        raise CandidatePublicationError("candidate_private_storage_required")
    if not isinstance(manifest, CandidateManifest):
        raise CandidatePublicationError("candidate_publication_manifest")
    try:
        validated = CandidateManifest.model_validate(manifest.model_dump(mode="json"))
        manifest_bytes = canonical_json(validated.model_dump(mode="json"))
    except (ValidationError, TypeError, ValueError):
        raise CandidatePublicationError("candidate_publication_manifest") from None
    payloads = dict(files)
    if set(payloads) != {entry.path for entry in validated.files}:
        raise CandidatePublicationError("candidate_publication_inventory")
    if not isinstance(runtime, bytes) or any(
        not isinstance(body, bytes) for body in payloads.values()
    ):
        raise CandidatePublicationError("candidate_publication_bytes")
    paths = {Path(name) for name in payloads} | {Path("manifest.json")}
    if "manifest.json" in payloads or any(
        "\x00" in str(path) or parent in paths for path in paths for parent in path.parents
    ):
        raise CandidatePublicationError("candidate_publication_path")
    for entry in validated.files:
        body = payloads[entry.path]
        if len(body) != entry.size_bytes:
            raise CandidatePublicationError("candidate_publication_size")
        if hashlib.sha256(body).hexdigest() != entry.sha256:
            raise CandidatePublicationError("candidate_publication_hash")
    deterministic = {"evidence/" + name: body for name, body in payloads.items()}
    deterministic["evidence/manifest.json"] = manifest_bytes
    output = storage.publish(relative, deterministic, runtime)
    return output / "evidence/manifest.json"
