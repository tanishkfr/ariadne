"""The efficiency policy: every behaviour-sensitive optimisation is flagged (AR-204 T13).

Defaults are deliberately conservative
--------------------------------------
An optimisation that changes what a model sees is a behaviour change, and a
behaviour change that reduces bytes is not a win until it has evidence behind it.
So every behaviour-sensitive optimisation here defaults to its pre-AR-204
behaviour, and the record says exactly what is on:

======================  =========================  =====================
setting                 values                     default
======================  =========================  =====================
``prompt_profile``      legacy | compact_v2        legacy
``tool_loading``        legacy | packs             legacy
``compaction``          off | structured_v1        off
``context_reduction``   off | adaptive             off (AR-202 decisions still run)
``history_format``      legacy | structured_v1      legacy
``routing_economics``   off | observe              off
``packet_order``        legacy | stable_prefix      legacy
``output_externalization`` off | threshold        threshold
======================  =========================  =====================

``output_externalization`` is the one default-on setting, and it qualifies
because it is *evidence-preserving* (AR-204 T6/§40): the complete output is still
written, the digests are unchanged, and only the model-facing view is bounded.

The config is recorded on the run state under ``efficiency`` with a digest, so a
report can always say which profile produced it.
"""

from __future__ import annotations

from typing import Mapping

from .contracts import ContractError
from .serialization import canonical_json, digest_text

PROMPT_PROFILES = ("legacy", "compact_v2")
TOOL_LOADING_PROFILES = ("legacy", "packs")
COMPACTION_PROFILES = ("off", "structured_v1")
CONTEXT_REDUCTION_PROFILES = ("off", "adaptive")
HISTORY_FORMAT_PROFILES = ("legacy", "structured_v1")
ROUTING_ECONOMICS_PROFILES = ("off", "observe")
PACKET_ORDER_PROFILES = ("legacy", "stable_prefix")
OUTPUT_EXTERNALIZATION_PROFILES = ("off", "threshold")

SETTING_VALUES = {
    "prompt_profile": PROMPT_PROFILES,
    "tool_loading": TOOL_LOADING_PROFILES,
    "compaction": COMPACTION_PROFILES,
    "context_reduction": CONTEXT_REDUCTION_PROFILES,
    "history_format": HISTORY_FORMAT_PROFILES,
    "routing_economics": ROUTING_ECONOMICS_PROFILES,
    "packet_order": PACKET_ORDER_PROFILES,
    "output_externalization": OUTPUT_EXTERNALIZATION_PROFILES,
}

DEFAULT_FLAGS: dict[str, str] = {
    "prompt_profile": "legacy",
    "tool_loading": "legacy",
    "compaction": "off",
    "context_reduction": "off",
    "history_format": "legacy",
    "routing_economics": "off",
    "packet_order": "legacy",
    "output_externalization": "threshold",
}

BEHAVIOUR_SENSITIVE: tuple[str, ...] = tuple(
    name for name in SETTING_VALUES if name != "output_externalization"
)
"""Settings that change what a model sees or how work is orchestrated.

They stay behind the flag until a control-vs-candidate measurement supports them.
"""

SAFE_DEFAULTS: tuple[str, ...] = ("output_externalization",)
"""Settings whose default-on state does not change model behaviour, only storage."""


def default_flags() -> dict:
    return dict(DEFAULT_FLAGS)


def config_problems(config: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(config, Mapping):
        return ["the efficiency configuration is not an object"]
    unknown = sorted(set(config) - set(SETTING_VALUES) - {"recorded_at", "digest"})
    if unknown:
        problems.append("unknown efficiency setting(s): " + ", ".join(unknown))
    for name, allowed in SETTING_VALUES.items():
        if name not in config:
            continue
        value = str(config.get(name, ""))
        if value not in allowed:
            problems.append(f"efficiency setting {name} has unsupported value {value!r}")
    return problems


def normalise(config: Mapping | None) -> dict:
    merged = dict(DEFAULT_FLAGS)
    for name, value in dict(config or {}).items():
        if name in SETTING_VALUES:
            merged[name] = str(value)
    return merged


def config_digest(config: Mapping) -> str:
    return digest_text(canonical_json(normalise(config)))


def efficiency_config(state: Mapping) -> dict:
    """The run's efficiency configuration, defaulted but never invented."""
    stored = state.get("efficiency") if isinstance(state, Mapping) else None
    merged = normalise(stored if isinstance(stored, Mapping) else None)
    return {**merged, "digest": config_digest(merged), "source": "run-state" if stored else "defaults"}


def set_efficiency_config(state: dict, **flags) -> dict:
    """Record the run's efficiency configuration. Invalid values are refused.

    Calling this with no settings resets the run to the declared defaults; calling
    it with settings merges them over the current configuration.
    """
    unknown = sorted(set(flags) - set(SETTING_VALUES))
    if unknown:
        raise ContractError("unknown efficiency setting(s): " + ", ".join(unknown))
    merged = normalise({**(efficiency_config(state) if flags else {}), **flags})
    problems = config_problems(merged)
    if problems:
        raise ContractError("efficiency configuration is invalid: " + "; ".join(problems))
    record = {**merged, "digest": config_digest(merged)}
    state["efficiency"] = record
    return record


def setting(state: Mapping, name: str) -> str:
    if name not in SETTING_VALUES:
        raise ContractError(f"unknown efficiency setting: {name!r}")
    return str(efficiency_config(state).get(name, DEFAULT_FLAGS[name]))


def enabled(state: Mapping, name: str, value: str) -> bool:
    return setting(state, name) == str(value)


def describe(state: Mapping) -> str:
    config = efficiency_config(state)
    active = [
        f"{name}={config[name]}" for name in sorted(SETTING_VALUES)
        if config[name] != DEFAULT_FLAGS[name]
    ]
    if not active:
        return f"efficiency defaults (digest {config['digest'][:12]}): every behaviour-sensitive optimisation is off"
    return f"efficiency overrides (digest {config['digest'][:12]}): " + ", ".join(active)


__all__ = [
    "PROMPT_PROFILES",
    "TOOL_LOADING_PROFILES",
    "COMPACTION_PROFILES",
    "CONTEXT_REDUCTION_PROFILES",
    "HISTORY_FORMAT_PROFILES",
    "ROUTING_ECONOMICS_PROFILES",
    "PACKET_ORDER_PROFILES",
    "OUTPUT_EXTERNALIZATION_PROFILES",
    "SETTING_VALUES",
    "DEFAULT_FLAGS",
    "BEHAVIOUR_SENSITIVE",
    "SAFE_DEFAULTS",
    "default_flags",
    "config_problems",
    "normalise",
    "config_digest",
    "efficiency_config",
    "set_efficiency_config",
    "setting",
    "enabled",
    "describe",
]
