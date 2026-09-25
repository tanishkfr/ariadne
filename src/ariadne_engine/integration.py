"""Versioned, provider-neutral integration contract for Ariadne consumers.

A consumer (an editor, a desktop app, a service) talks to Ariadne through this
module and the public API in :mod:`ariadne_engine.public`. The contract is
deliberately small and explicit:

* a protocol version and a capability list, both discoverable before any work;
* one request envelope carrying an operation and a payload, with unknown fields
  recorded and ignored -- never interpreted as permission;
* one response envelope whose ``authority`` field always names the engine, so a
  consumer cannot mint an approval, a validation or a verification;
* an adapter that translates consumer operations onto engine calls without
  bypassing the state transition authority.

This module imports no consumer, editor, network or paid provider code. A
consumer that requires an operation or capability this engine does not advertise
must treat the integration as unsupported; it must not guess.
"""

from __future__ import annotations

from . import api, contracts, package_version
from .contracts import ContractError

PROTOCOL_NAME = "ariadne-consumer"
PROTOCOL_VERSION = 1
MIN_SUPPORTED_VERSION = 1
MAX_SUPPORTED_VERSION = 1
ENVELOPE_SCHEMA = 1

OPERATIONS = (
    "describe",
    "open_project",
    "start_task",
    "inspect_task",
    "approve",
    "execute",
    "validate",
    "review",
    "recover",
    "inspect_capabilities",
    "get_events",
    "get_evidence",
    "inspect_migration",
    "apply_migration",
)

CAPABILITIES = (
    "lifecycle",
    "approval",
    "verification",
    "decision",
    "capability-evidence",
    "execution-identity",
    "events",
    "economics",
    "design-evidence",
    "recovery",
    "migration",
)

AUTHORITY_NOTE = (
    "Permission and verification evidence always originates in the engine. "
    "An envelope reports what the engine recorded; it never grants authority."
)


class IntegrationError(ContractError):
    """A consumer request the contract cannot honour. Nothing was changed."""


def describe() -> dict:
    """The complete, versioned description a consumer negotiates against."""
    return {
        "protocol": {
            "name": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
            "min_supported": MIN_SUPPORTED_VERSION,
            "max_supported": MAX_SUPPORTED_VERSION,
        },
        "engine": {
            "version": package_version(),
            "contract": contracts.ENGINE_CONTRACT,
            "run_schema": contracts.SCHEMA_RUN,
            "record_schema": contracts.SCHEMA_RECORD,
        },
        "envelope_schema": ENVELOPE_SCHEMA,
        "operations": list(OPERATIONS),
        "capabilities": list(CAPABILITIES),
        "authority": AUTHORITY_NOTE,
    }


def negotiate(request: dict) -> tuple[dict, list[str]]:
    """Check one consumer request before any operation runs.

    Returns ``(description, problems)``. An empty problem list means compatible.
    Unknown request fields are listed as ignored, never applied as authority.
    """
    if not isinstance(request, dict):
        return describe(), ["the negotiation request is not an object"]
    problems: list[str] = []
    version = request.get("protocol_version")
    if not isinstance(version, int):
        problems.append("protocol_version is required and must be an integer")
    elif not MIN_SUPPORTED_VERSION <= version <= MAX_SUPPORTED_VERSION:
        problems.append(
            f"protocol version {version} is outside the supported range "
            f"{MIN_SUPPORTED_VERSION}..{MAX_SUPPORTED_VERSION}"
        )
    required = request.get("required_capabilities") or []
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        problems.append("required_capabilities must be a list of strings")
    else:
        missing = sorted(set(required) - set(CAPABILITIES))
        if missing:
            problems.append("unsupported required capabilities: " + ", ".join(missing))
    optional = request.get("optional_capabilities") or []
    if not isinstance(optional, list) or any(not isinstance(item, str) for item in optional):
        problems.append("optional_capabilities must be a list of strings")
    known = {"protocol_version", "required_capabilities", "optional_capabilities", "consumer"}
    ignored = sorted(set(request) - known)
    description = describe()
    description["ignored_fields"] = ignored
    return description, problems


def _status(exit_code: int) -> str:
    return {0: "ok", 1: "refused", 2: "needs-human"}.get(int(exit_code), "unknown")


def _parse_json(message: str):
    import json

    text = message.strip()
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class ConsumerAdapter:
    """Translate a consumer's operations onto engine calls.

    The adapter owns no state and writes nothing itself. It refuses an
    incompatible protocol up front and returns one envelope per operation.
    """

    def __init__(
        self,
        client,
        *,
        consumer: str = "unknown",
        protocol_version: int = PROTOCOL_VERSION,
        required_capabilities=(),
        optional_capabilities=(),
    ) -> None:
        self.client = client
        self.consumer = consumer
        request = {
            "protocol_version": protocol_version,
            "required_capabilities": list(required_capabilities),
            "optional_capabilities": list(optional_capabilities),
            "consumer": consumer,
        }
        self.description, problems = negotiate(request)
        if problems:
            raise IntegrationError("; ".join(problems))

    @classmethod
    def from_runtime(cls, runtime_root=None, **options) -> "ConsumerAdapter":
        from . import public

        return cls(public.connect(runtime_root), **options)

    def call(self, operation: str, payload: dict | None = None) -> dict:
        if operation not in OPERATIONS:
            raise IntegrationError(
                f"unsupported operation {operation!r}; this engine supports: " + ", ".join(OPERATIONS)
            )
        payload = payload or {}
        handler = {
            "describe": self._describe,
            "open_project": self._open_project,
            "start_task": self._start_task,
            "inspect_task": self._inspect_task,
            "approve": self._approve,
            "execute": self._execute,
            "validate": self._validate,
            "review": self._review,
            "recover": self._recover,
            "inspect_capabilities": self._inspect_capabilities,
            "get_events": self._get_events,
            "get_evidence": self._get_evidence,
            "inspect_migration": self._inspect_migration,
            "apply_migration": self._apply_migration,
        }[operation]
        data, problems = handler(payload)
        result = data.pop("_result", None) if isinstance(data, dict) else None
        envelope = {
            "schema_version": ENVELOPE_SCHEMA,
            "protocol_version": PROTOCOL_VERSION,
            "operation": operation,
            "consumer": self.consumer,
            "status": _status(result.exit_code) if result is not None else ("ok" if not problems else "refused"),
            "message": result.message.strip() if result is not None else "",
            "data": data,
            "problems": list(problems),
            "authority": "engine",
        }
        return envelope

    def _call(self, name: str, **options):
        from . import public

        client = self.client
        if not isinstance(client, public.EngineClient):
            raise IntegrationError("the adapter needs an EngineClient from ariadne_engine.public.connect")
        return getattr(client, name)(**options)

    def _describe(self, payload: dict):
        return {"description": self.description}, []

    def _open_project(self, payload: dict):
        project = payload.get("project")
        if not project:
            return {"_result": _refused("open_project requires a project path")}, ["missing project"]
        result = self._call("status", project=project, as_json=True)
        if result.exit_code != 0:
            return {"_result": result, "exists": None}, []
        return {"_result": result, "exists": True, "state": _parse_json(result.message)}, []

    def _start_task(self, payload: dict):
        project = payload.get("project")
        if not project:
            return {"_result": _refused("start_task requires a project path")}, ["missing project"]
        result = self._call(
            "start_run",
            project=project,
            request=payload.get("request"),
            request_file=payload.get("request_file"),
            run_id=payload.get("run_id"),
            reasoner=payload.get("reasoner"),
        )
        return {"_result": result}, []

    def _inspect_task(self, payload: dict):
        result = self._call(
            "status",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            as_json=True,
        )
        return {"_result": result, "state": _parse_json(result.message)}, []

    def _approve(self, payload: dict):
        result = self._call(
            "approve_gate",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            gate=payload.get("gate"),
            identity=payload.get("identity"),
            note=payload.get("note"),
        )
        return {"_result": result}, []

    def _execute(self, payload: dict):
        result = self._call(
            "prepare_next",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            stage=payload.get("stage"),
        )
        return {"_result": result}, []

    def _validate(self, payload: dict):
        result = self._call(
            "validate_worker",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
        )
        return {"_result": result}, []

    def _review(self, payload: dict):
        result = self._call(
            "ingest_review",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            input=payload.get("input"),
            reviewer_identity=payload.get("reviewer_identity"),
            kind=payload.get("kind"),
        )
        return {"_result": result}, []

    def _recover(self, payload: dict):
        action = payload.get("action")
        if action:
            result = self._call(
                "apply_recovery",
                project=payload.get("project"),
                run_root=payload.get("run_root"),
                action=action,
                target=payload.get("target"),
                identity=payload.get("identity"),
                reason=payload.get("reason"),
            )
        else:
            result = self._call(
                "recovery_report",
                project=payload.get("project"),
                run_root=payload.get("run_root"),
            )
        return {"_result": result, "report": _parse_json(result.message)}, []

    def _inspect_capabilities(self, payload: dict):
        result = self._call(
            "inspect_capabilities",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            as_json=True,
        )
        return {"_result": result, "registry": _parse_json(result.message)}, []

    def _get_events(self, payload: dict):
        result = self._call(
            "engine_events",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
            limit=payload.get("limit", 50),
            as_json=True,
        )
        return {"_result": result, "events": _parse_json(result.message)}, []

    def _get_evidence(self, payload: dict):
        target = {"project": payload.get("project"), "run_root": payload.get("run_root")}
        task = self._call("status", as_json=True, **target)
        verification = self._call("verification_status", as_json=True, **target)
        capabilities = self._call("inspect_capabilities", as_json=True, **target)
        return {
            "_result": task,
            "task": _parse_json(task.message),
            "verification": _parse_json(verification.message),
            "capabilities": _parse_json(capabilities.message),
        }, []

    def _inspect_migration(self, payload: dict):
        result = self._call(
            "plan_migration",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
        )
        return {"_result": result}, []

    def _apply_migration(self, payload: dict):
        result = self._call(
            "apply_migration",
            project=payload.get("project"),
            run_root=payload.get("run_root"),
        )
        return {"_result": result}, []


def _refused(text: str) -> api.Result:
    return api.Result(exit_code=1, message=f"STOPPED: {text}\n")


CONTRACT_FIXTURES = {
    "happy_path": {
        "protocol_version": PROTOCOL_VERSION,
        "required_capabilities": ["lifecycle", "approval", "events"],
        "consumer": "fixture-consumer/1",
    },
    "unsupported_version": {
        "protocol_version": PROTOCOL_VERSION + 1,
        "required_capabilities": ["lifecycle"],
    },
    "missing_capability": {
        "protocol_version": PROTOCOL_VERSION,
        "required_capabilities": ["teleportation"],
    },
    "unknown_fields": {
        "protocol_version": PROTOCOL_VERSION,
        "required_capabilities": ["lifecycle"],
        "grant_approval": "G1",
        "trust_me": True,
    },
    "optional_capability_absent": {
        "protocol_version": PROTOCOL_VERSION,
        "required_capabilities": ["lifecycle"],
        "optional_capabilities": ["quantum-render"],
    },
}
"""Request shapes a consumer can replay; the release tests assert each outcome."""
