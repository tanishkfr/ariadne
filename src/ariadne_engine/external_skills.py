"""The trusted external skill ecosystem: discovery, inspection, and reuse (Ariadne 2.3C).

What this module is, and what it is not
---------------------------------------
Ariadne's native skills (:mod:`ariadne_engine.skills`) are reviewed with the
product, so loading one is safe by construction. An *external* skill comes from
outside that boundary: a catalogue directory the operator explicitly trusts, or
a previously installed and approved skill. This module makes such skills usable
without ever letting them become authority.

The rules it enforces, in order:

1. **Metadata before instructions.** Discovery reads only the bounded front
   matter of ``SKILL.md`` (the Agent Skills format: ``name``, ``description``,
   optional ``metadata``). Full instructions are read only at load time, for a
   skill that was already approved and installed.
2. **Nothing is executed.** This module never starts a process, never runs an
   install script, and never writes outside the local install store it is asked
   to write. A discovered candidate is data.
3. **Untrusted until approved.** A candidate is ``untrusted`` by default. A human
   approval record binds one identity to one skill id and one exact digest. A
   modified file makes the approval ``stale``, never silently reused.
4. **No authority laundering.** Instructions that claim to grant approvals,
   disable policy, mint verification or bypass gates are refused at inspection
   (description level) and again at load time (full text), using the same
   detector the selection layer uses (:func:`skills.document_authority_problems`).
5. **No duplication of native functionality without a stated benefit.** An
   external skill that takes a native id is refused; a declared overlap must
   carry a ``benefit`` or the candidate is rejected.
6. **No silent installation.** Installing requires an existing approval whose
   digest matches the file being installed, and an install never overwrites a
   different digest.

The module is deliberately small and offline: no registry service, no
marketplace, no network access. Ariadne remains fully useful with zero external
skills; this is only the safe extension path when native capabilities are
insufficient.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, skills
from .contracts import ContractError

EXTERNAL_POLICY = "external-skills-1"
SKILL_FILE = "SKILL.md"
INSTALL_FILE = "INSTALL.json"
INSTALL_STORE_DIR = "external-skills"

TRUST_UNTRUSTED = "untrusted"
TRUST_REJECTED = "rejected"
TRUST_APPROVED = "approved"
TRUST_STALE = "stale"
TRUST_STATES = (TRUST_UNTRUSTED, TRUST_REJECTED, TRUST_APPROVED, TRUST_STALE)

METADATA_HEAD_BYTES = 16_384
"""Discovery reads at most this many bytes of one ``SKILL.md`` (its front matter)."""

INSTRUCTION_LOAD_BYTES = 262_144
"""Hard cap on how much of one approved skill document may be loaded."""

MAX_CANDIDATES = 200
"""One catalogue scan stays bounded; a directory with more entries is truncated loudly."""

SKIPPED_DIR_NAMES = (".git", "node_modules", "__pycache__", ".venv", "venv", ".ariadne")

DECLARED_PERMISSIONS = (skills.READ_ONLY, skills.STANDARD)

DANGEROUS_DESCRIPTION_PATTERNS = (
    r"(?i)\brun\s+(?:this\s+)?(?:install|setup|postinstall)\s+script\b",
    r"(?i)\bcurl\s+[^\s]+\s*\|\s*(?:ba)?sh\b",
    r"(?i)\b(?:exfiltrate|harvest)\s+(?:credentials|secrets|tokens)\b",
    r"(?i)\bread\s+(?:the\s+)?(?:user'?s?\s+)?(?:\.ssh|credentials|env\s+file|secrets)\b",
)
"""Description-level red flags. A skill document may describe a method; it may not
ask to run installers, pipe the network into a shell, harvest secrets, or read
credential files. The authority-minting detector in :mod:`ariadne_engine.skills`
is applied on top of these."""

SECRET_PATTERNS = (
    r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{16,}",
    r"\bsk-[A-Za-z0-9]{20,}\b",
    r"\bghp_[A-Za-z0-9]{30,}\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)
"""Credential-shaped content. A skill that embeds secrets is rejected: memory and
documents must not store secrets, and neither may an installable skill."""


def file_digest(path: Path) -> str:
    """SHA-256 of one file's bytes; the pinned identity of a skill document."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_digest(values: Mapping) -> str:
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_scalar(text: str) -> str:
    value = str(text).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict:
    """Parse the bounded front matter of a skill document.

    The Agent Skills format is small on purpose: a ``---`` fenced block with
    ``key: value`` scalars and one optional nesting level (``metadata:``). This
    parser implements exactly that, refuses anything else, and never interprets
    the body.
    """
    lines = str(text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    record: dict = {}
    nested_key = ""
    for line in lines[1:]:
        if line.strip() == "---":
            return record
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            if not nested_key:
                continue
            key, _, value = line.strip().partition(":")
            if key and value:
                nested = record.setdefault(nested_key, {})
                if isinstance(nested, dict):
                    nested[key.strip()] = _parse_scalar(value)
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if not value:
            record[key] = {}
            nested_key = key
        else:
            record[key] = _parse_scalar(value)
            nested_key = ""
    return {}


def _declared_list(value) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def read_candidate_head(path: Path) -> dict:
    """The bounded metadata view of one candidate skill directory.

    Reads at most :data:`METADATA_HEAD_BYTES` of ``SKILL.md``; the file's full
    digest is computed streaming, and the instruction body is not parsed.
    """
    skill_file = Path(path) / SKILL_FILE
    if not skill_file.is_file():
        return {"available": False, "reason": f"{SKILL_FILE} is absent"}
    try:
        with open(skill_file, "rb") as handle:
            head = handle.read(METADATA_HEAD_BYTES)
        digest = file_digest(skill_file)
        size = skill_file.stat().st_size
    except OSError as error:
        return {"available": False, "reason": f"{SKILL_FILE} could not be read: {error}"}
    text = head.decode("utf-8", errors="replace")
    front = parse_front_matter(text)
    meta = front.get("metadata") if isinstance(front.get("metadata"), Mapping) else {}
    return {
        "available": True,
        "path": str(Path(path)),
        "id": str(front.get("name", "")).strip(),
        "description": str(front.get("description", "")).strip(),
        "version": str(meta.get("version", "")).strip(),
        "publisher": str(meta.get("publisher", "")).strip(),
        "license": str(meta.get("license", "")).strip(),
        "permission": str(meta.get("permission", skills.READ_ONLY)).strip() or skills.READ_ONLY,
        "families": _declared_list(meta.get("families")),
        "workflows": _declared_list(meta.get("workflows")),
        "requires": _declared_list(meta.get("requires")),
        "overlaps": _declared_list(meta.get("overlaps")),
        "benefit": str(meta.get("benefit", "")).strip(),
        "documents": _declared_list(meta.get("documents")),
        "digest": digest,
        "bytes": int(size),
        "head_bytes": len(head),
    }


def discover_catalog(catalog: Path, *, limit: int = MAX_CANDIDATES) -> dict:
    """Scan one explicitly trusted catalogue directory for candidate skills.

    Discovery writes nothing, starts nothing, and reads only bounded metadata
    from each candidate's ``SKILL.md``. An unavailable catalogue is a fact to
    report, not an error: Ariadne stays fully useful without external skills.
    """
    root = Path(catalog)
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "policy": EXTERNAL_POLICY,
        "catalog": str(root),
        "available": False,
        "reason": "",
        "candidates": [],
        "truncated": False,
    }
    if not root.is_dir():
        record["reason"] = "the catalogue directory does not exist"
        return record
    record["available"] = True
    try:
        children = sorted(
            (item for item in root.iterdir() if item.is_dir()),
            key=lambda item: item.name,
        )
    except OSError as error:
        record["available"] = False
        record["reason"] = f"the catalogue could not be listed: {error}"
        return record
    candidates = []
    for child in children:
        if child.name in SKIPPED_DIR_NAMES:
            continue
        if len(candidates) >= int(limit):
            record["truncated"] = True
            break
        head = read_candidate_head(child)
        if not head.get("available"):
            continue
        candidates.append(head)
    record["candidates"] = candidates
    record["count"] = len(candidates)
    return record


def evaluate_candidate(
    candidate: Mapping,
    *,
    native_registry: Mapping | None = None,
    host: Mapping | None = None,
    other_sources: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """The evaluation record for one discovered candidate, metadata only.

    This is what a human reviews before approving anything. It states, for one
    skill: identity, source, licence, pinned digest, required tools and
    capabilities, host compatibility, declared permissions, applicability,
    overlap with native skills, context cost, and every instruction-conflict
    signal the detector can see without loading the body.
    """
    registry = dict(native_registry or skills.SKILL_REGISTRY)
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "policy": EXTERNAL_POLICY,
        "evaluated_at": contracts.utc_now(),
        "skill_id": str(candidate.get("id", "")),
        "description": str(candidate.get("description", "")),
        "version": str(candidate.get("version", "")),
        "publisher": str(candidate.get("publisher", "")),
        "license": str(candidate.get("license", "")),
        "source": str(candidate.get("path", "")),
        "digest": str(candidate.get("digest", "")),
        "digest_algo": "sha256",
        "bytes": int(candidate.get("bytes", 0) or 0),
        "context_cost": {
            "document_bytes": int(candidate.get("bytes", 0) or 0),
            "documents": list(candidate.get("documents") or []),
        },
        "requires_capabilities": list(candidate.get("requires", [])),
        "host_compatibility": {},
        "permission": str(candidate.get("permission", skills.READ_ONLY)),
        "families": list(candidate.get("families", [])),
        "workflows": list(candidate.get("workflows", [])),
        "overlaps": list(candidate.get("overlaps", [])),
        "benefit": str(candidate.get("benefit", "")),
        "authority_problems": [],
        "danger_problems": [],
        "secret_problems": [],
        "conflict_problems": [],
        "problems": [],
        "status": TRUST_UNTRUSTED,
    }
    problems = record["problems"]
    skill_id = record["skill_id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", skill_id):
        problems.append("the skill declares no stable identifier (lowercase letters, digits, dashes)")
    if not record["description"]:
        problems.append("the skill declares no description")
    if not re.fullmatch(r"\d+\.\d+\.\d+", record["version"] or ""):
        problems.append("the skill declares no semantic version")
    if not record["license"]:
        problems.append("the skill declares no licence; an unlicensed skill cannot be approved")
    if not re.fullmatch(r"[0-9a-f]{64}", record["digest"]):
        problems.append("the skill has no pinned content digest")
    if record["permission"] not in DECLARED_PERMISSIONS:
        problems.append(f"the skill declares an unknown permission level: {record['permission']!r}")
    if not record["families"]:
        problems.append("the skill declares no applicable intent families")
    else:
        import ariadne_engine.tasks as _tasks  # local import: avoids an import cycle

        unknown = sorted(set(record["families"]) - set(_tasks.INTENT_FAMILIES))
        if unknown:
            problems.append("the skill declares unknown intent families: " + ", ".join(unknown))
    if record["workflows"]:
        unknown = sorted(set(record["workflows"]) - set(skills.WORKFLOWS))
        if unknown:
            problems.append("the skill declares unknown workflows: " + ", ".join(unknown))
    known_capabilities = set()
    try:
        from . import tooling as _tooling

        known_capabilities = set(_tooling.CORE_CAPABILITIES) | {"capture", "reference-research", "design-direction"}
    except Exception:  # pragma: no cover - tooling is part of the package
        pass
    for capability in record["requires_capabilities"]:
        if known_capabilities and capability not in known_capabilities:
            problems.append(f"the skill requires unknown capability {capability!r}")

    host_view = skills.host_capabilities(host) if not (isinstance(host, Mapping) and "values" in host) else host
    compatibility = {}
    for capability in record["requires_capabilities"]:
        status = str((dict(host_view.get("values") or {}).get(capability) or {}).get("status", ""))
        compatibility[capability] = status or "ABSENT"
    record["host_compatibility"] = compatibility

    text = record["description"]
    authority = skills.document_authority_problems(text)
    record["authority_problems"] = authority
    problems.extend(authority)
    for pattern in DANGEROUS_DESCRIPTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            record["danger_problems"].append(
                f"the description asks for a dangerous operation: {match.group(0)!r}"
            )
    problems.extend(record["danger_problems"])
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            record["secret_problems"].append("the description contains credential-shaped content")
            break
    problems.extend(record["secret_problems"])

    if skill_id in registry:
        record["conflict_problems"].append(
            f"the skill id {skill_id!r} is already taken by a native Ariadne skill; "
            "an external skill may never shadow a native one"
        )
    for native_id in record["overlaps"]:
        if native_id not in registry:
            record["conflict_problems"].append(
                f"the skill declares an overlap with unknown skill {native_id!r}"
            )
        elif not record["benefit"]:
            record["conflict_problems"].append(
                f"the skill overlaps native {native_id!r} without a stated benefit; "
                "duplicating native functionality is refused"
            )
    if other_sources:
        for other_id, digests in sorted(other_sources.items()):
            if other_id == skill_id and record["digest"] not in set(digests):
                record["conflict_problems"].append(
                    f"another catalogue provides {skill_id!r} at a different digest; "
                    "two versions of one skill may not be approved together"
                )
    problems.extend(record["conflict_problems"])
    if problems:
        record["status"] = TRUST_REJECTED
    return record


def evaluation_problems(record: Mapping) -> list[str]:
    """Structural validation of one evaluation record (fail closed)."""
    problems = contracts.adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if str(record.get("policy", "")) != EXTERNAL_POLICY:
        problems.append("external skill evaluation carries an unknown policy")
    if str(record.get("status", "")) not in TRUST_STATES:
        problems.append(f"external skill evaluation has an unsupported status: {record.get('status')!r}")
    if record.get("status") == TRUST_REJECTED and not record.get("problems"):
        problems.append("a rejected evaluation records no problem")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("digest", ""))):
        problems.append("external skill evaluation has no pinned digest")
    return problems


def approval_record(
    evaluation: Mapping,
    *,
    identity: str,
    scope_families: Sequence[str] = (),
    scope_workflows: Sequence[str] = (),
    note: str = "",
    catalog: str = "",
) -> dict:
    """One human approval binding an identity to one exact skill digest.

    An approval is not a permission grant for the *project*: it authorises this
    skill document, at this digest, for the declared families and workflows, and
    nothing else. It never widens Ariadne's authorization model.
    """
    if not str(identity).strip():
        raise ContractError("an external skill approval requires the human identity granting it")
    if str(evaluation.get("status")) == TRUST_REJECTED:
        raise ContractError(
            "a rejected candidate cannot be approved: "
            + "; ".join(str(item) for item in evaluation.get("problems") or [])
        )
    digest = str(evaluation.get("digest", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ContractError("an external skill approval needs the candidate's pinned digest")
    return {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "policy": EXTERNAL_POLICY,
        "approval_id": contracts.new_record_id("xsk"),
        "skill_id": str(evaluation.get("skill_id", "")),
        "digest": digest,
        "identity": str(identity).strip(),
        "approved_at": contracts.utc_now(),
        "scope": {
            "families": sorted(str(item) for item in (scope_families or evaluation.get("families") or ())),
            "workflows": sorted(str(item) for item in (scope_workflows or evaluation.get("workflows") or ())),
        },
        "source": str(catalog or evaluation.get("source", "")),
        "note": str(note),
    }


def approval_problems(record: Mapping) -> list[str]:
    """Structural validation of one approval record (fail closed)."""
    problems = contracts.adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"xsk_[0-9TZ]+_[0-9a-f]{8}", str(record.get("approval_id", ""))):
        problems.append("external skill approval has a malformed id")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("digest", ""))):
        problems.append("external skill approval has no pinned digest")
    for name in ("skill_id", "identity", "approved_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"external skill approval has no {name}")
    scope = record.get("scope")
    if not isinstance(scope, Mapping):
        problems.append("external skill approval has no scope")
    return problems


def approval_status(approval: Mapping, *, digest: str, skill_id: str) -> str:
    """The current trust state of one approval against the bytes on disk."""
    if str(approval.get("skill_id", "")) != str(skill_id):
        return TRUST_UNTRUSTED
    if str(approval.get("digest", "")) != str(digest):
        return TRUST_STALE
    return TRUST_APPROVED


def install_skill(
    candidate_dir: Path,
    store_root: Path,
    *,
    approval: Mapping,
    skill_id: str,
) -> dict:
    """Copy one approved skill into the local install store.

    The install boundary is explicit and narrow: the approval's digest must
    match the bytes being copied, an existing install of a *different* digest is
    refused rather than overwritten, and only the skill directory's files are
    copied (dot-directories and toolchain residue are skipped). No script in the
    skill is ever executed; installation is a copy, not a build.
    """
    problems = approval_problems(approval)
    if problems:
        raise ContractError("the external skill approval is malformed: " + "; ".join(problems))
    source = Path(candidate_dir)
    skill_file = source / SKILL_FILE
    if not skill_file.is_file():
        raise ContractError(f"the candidate has no {SKILL_FILE} to install")
    digest = file_digest(skill_file)
    if digest != str(approval.get("digest", "")):
        raise ContractError(
            "the skill file changed since it was approved; the approval is stale and a fresh "
            "human approval of the new digest is required"
        )
    if str(approval.get("skill_id", "")) != str(skill_id):
        raise ContractError("the approval names a different skill id than the install request")
    target = Path(store_root) / str(skill_id)
    install_path = target / INSTALL_FILE
    if install_path.is_file():
        try:
            existing = json.loads(install_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        installed_copy = target / SKILL_FILE
        try:
            installed_digest = file_digest(installed_copy)
        except OSError:
            installed_digest = ""
        if str(existing.get("digest", "")) == digest and installed_digest == digest:
            return {"installed": False, "reason": "the same digest is already installed", "target": str(target)}
        if installed_digest and installed_digest != str(existing.get("digest", "")):
            raise ContractError(
                f"the installed copy of {skill_id!r} was modified after install; refusing to replace "
                "tampered bytes silently. Remove the managed install first."
            )
        raise ContractError(
            f"a different revision of {skill_id!r} is already installed; uninstall or re-approve "
            "before replacing it"
        )
    if target.exists():
        raise ContractError(f"the install target already exists but is not a managed skill: {target}")
    target.mkdir(parents=True, exist_ok=False)
    files: dict[str, str] = {}
    for item in sorted(source.rglob("*")):
        if any(part in SKIPPED_DIR_NAMES for part in item.relative_to(source).parts):
            continue
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, destination)
        files[relative.as_posix()] = file_digest(destination)
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "policy": EXTERNAL_POLICY,
        "skill_id": str(skill_id),
        "digest": digest,
        "approval_id": str(approval.get("approval_id", "")),
        "installed_at": contracts.utc_now(),
        "source": str(source),
        "files": files,
    }
    install_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"installed": True, "reason": "", "target": str(target), "record": record}


def installed_skills(store_root: Path) -> list[dict]:
    """Every managed install record in the store (read-only)."""
    root = Path(store_root)
    records = []
    if not root.is_dir():
        return records
    for child in sorted(root.iterdir()):
        install_path = child / INSTALL_FILE
        if not child.is_dir() or not install_path.is_file():
            continue
        try:
            record = json.loads(install_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, Mapping):
            records.append(dict(record))
    return records


def verify_install(store_root: Path, skill_id: str) -> list[str]:
    """Problems with one installed skill: missing files, changed bytes."""
    target = Path(store_root) / str(skill_id)
    install_path = target / INSTALL_FILE
    if not install_path.is_file():
        return [f"{skill_id!r} is not installed in the store"]
    try:
        record = json.loads(install_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"the install record could not be read: {error}"]
    problems = []
    for relative, digest in sorted(dict(record.get("files") or {}).items()):
        path = target / relative
        if not path.is_file():
            problems.append(f"installed file is missing: {relative}")
            continue
        if file_digest(path) != digest:
            problems.append(f"installed file changed after install: {relative}")
    return problems


def load_instructions(store_root: Path, skill_id: str, *, limit: int = INSTRUCTION_LOAD_BYTES) -> dict:
    """The full instruction text of one *installed* skill, scanned on load.

    Loading is the expensive step, so it happens only for an installed skill,
    and the text passes the authority detector again before a caller may act on
    it. A skill whose body tries to mint authority is refused here even if its
    description was clean.
    """
    target = Path(store_root) / str(skill_id) / SKILL_FILE
    if not target.is_file():
        return {"loaded": False, "reason": f"{skill_id!r} has no installed {SKILL_FILE}", "problems": []}
    try:
        with open(target, "rb") as handle:
            raw = handle.read(int(limit) + 1)
    except OSError as error:
        return {"loaded": False, "reason": f"{SKILL_FILE} could not be read: {error}", "problems": []}
    truncated = len(raw) > int(limit)
    text = raw[: int(limit)].decode("utf-8", errors="replace")
    problems = skills.document_authority_problems(text)
    for pattern in DANGEROUS_DESCRIPTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            problems.append(f"the instructions ask for a dangerous operation: {match.group(0)!r}")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            problems.append("the instructions contain credential-shaped content")
            break
    if problems:
        return {
            "loaded": False,
            "reason": "the skill instructions were refused by the trust checks",
            "problems": problems,
        }
    return {
        "loaded": True,
        "reason": "",
        "text": text,
        "truncated": truncated,
        "digest": file_digest(target),
        "problems": [],
    }


def registry_entries(
    *,
    store_root: Path,
    approvals: Sequence[Mapping] | Mapping,
    native_registry: Mapping | None = None,
) -> tuple[dict, list[dict]]:
    """Selection-registry entries for approved, installed, verified skills.

    Returns ``(entries, status_rows)``. An entry is emitted only when an
    approval matches the installed digest exactly; anything else is a status row
    explaining why the skill is *not* selectable. The entries carry
    ``source=external`` and a declared permission, so the existing selector
    still refuses them unless the caller passes the matching approval id in
    ``approved_external`` — approval here is an input, never an override.
    """
    registry = dict(native_registry or skills.SKILL_REGISTRY)
    rows: list[dict] = []
    entries: dict[str, dict] = {}
    approval_list = (
        list(approvals.values())
        if isinstance(approvals, Mapping)
        else [dict(item) for item in approvals or ()]
    )
    for record in sorted(
        [item for item in approval_list if str(item.get("skill_id", ""))],
        key=lambda item: str(item.get("skill_id", "")),
    ):
        skill_id = str(record.get("skill_id", ""))
        installed = Path(store_root) / skill_id
        problems = verify_install(store_root, skill_id)
        if problems:
            try:
                current_digest = file_digest(installed / SKILL_FILE)
            except OSError:
                current_digest = ""
            if current_digest and current_digest != str(record.get("digest", "")):
                rows.append({
                    "skill_id": skill_id,
                    "status": TRUST_STALE,
                    "reasons": problems + [
                        "the installed bytes no longer match the approved digest; a fresh human "
                        "approval of the new revision is required"
                    ],
                })
            else:
                rows.append({"skill_id": skill_id, "status": TRUST_UNTRUSTED, "reasons": problems})
            continue
        digest = str(record.get("digest", ""))
        try:
            current = file_digest(installed / SKILL_FILE)
        except OSError:
            current = ""
        state = approval_status(record, digest=current, skill_id=skill_id)
        if state != TRUST_APPROVED:
            rows.append({
                "skill_id": skill_id,
                "status": TRUST_STALE,
                "reasons": ["the installed skill no longer matches the approved digest"],
            })
            continue
        if skill_id in registry:
            rows.append({
                "skill_id": skill_id,
                "status": TRUST_REJECTED,
                "reasons": ["the id collides with a native skill; native skills always win"],
            })
            continue
        try:
            install_record = json.loads((installed / INSTALL_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            install_record = {}
        body = read_candidate_head(installed)
        scope = dict(record.get("scope") or {})
        entry = {
            "id": skill_id,
            "version": str(body.get("version", "")) or "0.0.0",
            "title": str(body.get("id", skill_id)) or skill_id,
            "purpose": str(body.get("description", "")),
            "workflows": tuple(body.get("workflows") or ("task",)),
            "families": tuple(body.get("families") or ()),
            "mandatory_for": (),
            "requires_capabilities": tuple(body.get("requires") or ()),
            "permission": str(body.get("permission", skills.READ_ONLY)),
            "preconditions": (),
            "tools": (),
            "context": (f"{INSTALL_STORE_DIR}/{skill_id}/{SKILL_FILE}",),
            "outputs": ("the method the skill document describes",),
            "evidence": ("the skill document, at its approved digest",),
            "incompatibilities": (),
            "strategy_slots": {},
            "source": skills.EXTERNAL_SOURCE,
            "owner": str(body.get("publisher", "")) or "external",
            "_external": {
                "approval_id": str(record.get("approval_id", "")),
                "digest": digest,
                "scope": scope,
                "installed_at": str(install_record.get("installed_at", "")),
            },
        }
        entries[skill_id] = entry
        rows.append({
            "skill_id": skill_id,
            "status": TRUST_APPROVED,
            "reasons": [],
            "digest": digest,
            "approval_id": str(record.get("approval_id", "")),
            "scope": scope,
        })
    return entries, rows


def merged_registry(
    *,
    store_root: Path,
    approvals: Sequence[Mapping] | Mapping,
    native_registry: Mapping | None = None,
) -> tuple[dict, list[dict]]:
    """The selector registry: native skills plus verified external entries.

    Native entries always win an id collision, and external entries are still
    excluded by :func:`skills.select_skills` unless the caller lists their id in
    ``approved_external``. Merging therefore widens *inspection* only; it grants
    nothing.
    """
    native = dict(native_registry or skills.SKILL_REGISTRY)
    external, rows = registry_entries(store_root=store_root, approvals=approvals, native_registry=native)
    merged = dict(native)
    for skill_id, entry in external.items():
        merged.setdefault(skill_id, entry)
    return merged, rows


def candidate_briefing(
    *,
    selection: Mapping,
    catalogs: Sequence[Path],
    native_registry: Mapping | None = None,
    host: Mapping | None = None,
    store_root: Path | None = None,
    approvals: Sequence[Mapping] = (),
    limit: int = 5,
) -> dict:
    """Mention discovered candidates only when native capabilities fell short.

    This is the 'newly discovered candidate skills when existing capabilities
    are insufficient' path: when a selection records capability gaps or an empty
    choice for a family, the briefing lists matching catalogue candidates for a
    human to inspect and, if they choose, approve. It never selects them and
    never installs anything.
    """
    gaps = list(selection.get("gaps") or ())
    chosen = list(selection.get("selected") or ())
    insufficient = bool(gaps) or not chosen
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "policy": EXTERNAL_POLICY,
        "needed": bool(insufficient),
        "reason": (
            "the native selection recorded capability gaps or no applicable skill"
            if insufficient
            else "native skills cover this task; external candidates are not needed"
        ),
        "catalogs": [],
        "candidates": [],
        "installed": [],
    }
    if store_root is not None:
        record["installed"] = [
            {"skill_id": str(row.get("skill_id", "")), "status": str(row.get("status", ""))}
            for row in installed_skills(store_root)
        ]
    if not insufficient:
        return record
    family = str(selection.get("intent", ""))
    seen: set[str] = set()
    for catalog in catalogs:
        scan = discover_catalog(Path(catalog))
        record["catalogs"].append({"path": str(catalog), "available": scan["available"], "reason": scan["reason"]})
        if not scan["available"]:
            continue
        for candidate in scan["candidates"]:
            skill_id = str(candidate.get("id", ""))
            if not skill_id or skill_id in seen:
                continue
            if family and family not in (candidate.get("families") or ()):
                continue
            evaluation = evaluate_candidate(
                candidate, native_registry=native_registry, host=host
            )
            if str(evaluation.get("status")) == TRUST_REJECTED:
                continue
            seen.add(skill_id)
            record["candidates"].append(evaluation)
            if len(record["candidates"]) >= int(limit):
                break
        if len(record["candidates"]) >= int(limit):
            break
    return record


def describe(rows: Sequence[Mapping]) -> str:
    """One operator sentence over registry status rows."""
    if not rows:
        return "no external skills are installed"
    approved = sum(1 for row in rows if str(row.get("status")) == TRUST_APPROVED)
    other = len(rows) - approved
    return f"{approved} approved external skill(s)" + (f"; {other} needing attention" if other else "")


__all__ = [
    "EXTERNAL_POLICY",
    "SKILL_FILE",
    "INSTALL_FILE",
    "INSTALL_STORE_DIR",
    "TRUST_UNTRUSTED",
    "TRUST_REJECTED",
    "TRUST_APPROVED",
    "TRUST_STALE",
    "TRUST_STATES",
    "METADATA_HEAD_BYTES",
    "INSTRUCTION_LOAD_BYTES",
    "MAX_CANDIDATES",
    "file_digest",
    "parse_front_matter",
    "read_candidate_head",
    "discover_catalog",
    "evaluate_candidate",
    "evaluation_problems",
    "approval_record",
    "approval_problems",
    "approval_status",
    "install_skill",
    "installed_skills",
    "verify_install",
    "load_instructions",
    "registry_entries",
    "merged_registry",
    "candidate_briefing",
    "describe",
]
