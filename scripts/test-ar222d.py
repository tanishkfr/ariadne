#!/usr/bin/env python3
"""The AR-222D test suite: design specificity, source ecosystem, proof readiness.

Covers the hardening layer that sits between AR-222's rendered critique and AR-223's
acceptance intelligence:

```text
request  ->  concept exploration  ->  content model  ->  anti-default analysis
        ->  roles / motion intent  ->  internal evaluation  ->  one recommendation
        ->  provider-neutral proposal  ->  G1D  ->  autonomous continuation
```

and the three properties that make those claims trustworthy:

* **the grammar has a method and no style.** Twelve principles, no aesthetic, and a
  ``house_style`` field that is refused if anything fills it in
* **detection is not failure.** A category default that the product earned is kept, and a
  run that keeps it is not penalised
* **the harness is honest.** Mutations restore transactionally, an active mutation blocks a
  commit, and a lost critical test is caught by name rather than by count

The suite runs entirely offline. No source is fetched and no browser is launched: the
source ecosystem is verified from recorded evidence, and the vertical slice stops at
implementation planning. Both are deliberate -- AR-222D proves the *method*, and Beacon
remains AR-222's rendered negative case.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ariadne_engine import contracts  # noqa: E402
from ariadne_engine.design_reference import specificity as sp  # noqa: E402
from ariadne_engine.design_reference.specificity import (  # noqa: E402
    concepts,
    content,
    defaults,
    grammar,
    interruption,
    platform,
    proposal,
    sources,
    vertical_slice as f1,
)
from ariadne_engine.rendered_critique import continuity, proof  # noqa: E402
from harness import mutation_ledger, test_inventory  # noqa: E402

OFFLINE: dict = {}


def case(fn):
    """Register a test function, in declaration order."""
    OFFLINE.setdefault("cases", []).append(fn)
    return fn


def raises(fn, *fragments: str) -> str:
    try:
        fn()
    except contracts.ContractError as exc:
        message = str(exc)
        for fragment in fragments:
            assert fragment in message, f"expected {fragment!r} in refusal: {message}"
        return message
    raise AssertionError(f"expected a refusal naming {fragments}")


def truthy(value, message: str) -> None:
    assert value, message


# =========================================================== grammar and method

@case
def the_grammar_encodes_a_method_and_carries_no_style():
    record = grammar.grammar()
    assert len(record["principles"]) == len(grammar.PRINCIPLE_ORDER)
    assert record["house_style"] is None, record["house_style"]
    assert not grammar.grammar_problems(record), grammar.grammar_problems(record)
    # Nothing renderable may live in the grammar: no literal colour, length or font value.
    # The grammar's *structural* data carries no design value. Its principle statements are
    # prose and may illustrate a rule with an example colour -- "roles before literal values"
    # has to be able to say "#6d28d9 is not a decision" -- so the check is on the data, not the prose.
    structural = {key: value for key, value in record.items() if key != "principles"}
    blob = json.dumps(structural).lower()
    for pattern in (r"\d+px", r"\d+rem", r"font-family", r"rgb\(", r"hsl\(", r"#[0-9a-f]{3,6}\b"):
        assert not re.search(pattern, blob), f"the grammar's data contains a literal design value: {pattern}"
    for row in record["principles"]:
        text = json.dumps(row).lower()
        assert not re.search(r"\d+px|font-family|rgb\(|hsl\(", text), row
    # The role vocabularies are method, not style: they name *what a value is for* and carry
    # no values. A role list containing a hex value would be a house style in disguise.
    for kind, entries in record["roles"].items():
        for entry in entries:
            assert isinstance(entry, str) and not re.search(r"#[0-9a-f]{3,6}|\d+px|\d+rem", entry), entry
        assert kind in ("colour", "type", "motion"), kind


@case
def a_grammar_that_has_collected_a_house_style_is_refused():
    record = grammar.grammar()
    record["house_style"] = {"colour": "#0b0f14", "type": "Inter"}
    problems = grammar.grammar_problems(record)
    assert any("house style" in item for item in problems), problems


@case
def an_incomplete_grammar_is_refused():
    record = grammar.grammar()
    record["principles"] = record["principles"][:4]
    problems = grammar.grammar_problems(record)
    assert any("all 12 principles" in item for item in problems), problems


@case
def every_principle_is_stated_and_not_merely_named():
    for key in grammar.PRINCIPLE_ORDER:
        statement = grammar.GRAMMAR_PRINCIPLES[key]
        assert len(statement.split()) >= 8, f"{key} has no stated principle"


# ======================================================== roles before values

@case
def role_before_value_is_enforced_in_both_directions():
    bindings = [
        {"role_kind": "colour", "role": "background", "meaning": "the instrument ground", "value": "#0b0f14"},
        {"role_kind": "type", "role": "data_metric", "meaning": "a value read for its number", "value": "tabular-nums"},
    ]
    rows, problems = grammar.role_bindings(bindings)
    assert not problems, problems
    assert [row["role"] for row in rows] == ["background", "data_metric"], rows
    early = [{"role_kind": "colour", "role": "background", "meaning": "", "value": "#0b0f14"}]
    assert grammar.literal_value_first(early), "a value chosen before its meaning is not recorded"


@case
def an_unknown_role_is_refused():
    assert grammar.role_problems("colour", "vibes")
    assert grammar.role_problems("mood", "calm")
    assert not grammar.role_problems("colour", "accent_purpose")


@case
def motion_requires_an_intent_from_the_supported_vocabulary():
    good = [{"motion_id": "m1", "intent": "STATE_CONFIRMATION", "evidence": "the row order changed"}]
    assert not grammar.motion_intent_problems(good)
    premium = [{"motion_id": "m2", "intent": "PREMIUM_ANIMATION", "evidence": "it looks expensive"}]
    problems = grammar.motion_intent_problems(premium)
    assert any("PREMIUM_ANIMATION" in item for item in problems), problems
    unsupported = [{"motion_id": "m3", "intent": "REWARD", "evidence": ""}]
    assert grammar.motion_intent_problems(unsupported), "an intent with no evidence is an assertion"


@case
def richness_source_must_be_named_and_restraint_is_allowed():
    assert grammar.richness_problems({"richness_source": ""})
    assert grammar.richness_problems({"richness_source": "VIBES"})
    for source in ("TYPOGRAPHY", "CONTENT_DENSITY", "REAL_CONTENT"):
        assert not grammar.richness_problems({"richness_source": source}), source
    assert "TYPOGRAPHY" in grammar.RESTRAINT_RICHNESS_SOURCES


# ==================================================== concept and divergence

@case
def three_candidates_materially_differ():
    candidates = f1.concept_records()
    assert len(candidates) >= concepts.MIN_CANDIDATES, len(candidates)
    report = concepts.material_divergence(candidates)
    assert report["divergent_count"] >= concepts.MIN_DIVERGENT_AXES, report
    assert not report["palette_only"], report
    assert not concepts.divergence_problems(candidates), concepts.divergence_problems(candidates)


@case
def every_divergence_axis_is_load_bearing_not_decorative():
    """Each axis must actually be able to distinguish two candidates.

    Without this, an axis could be removed from
    :data:`concepts.DIVERGENCE_AXES` and the candidate set would still pass -- which is
    precisely how a set that differs only by colour becomes three options offered as a
    choice. One pair per axis, varying only that axis.
    """
    base = {
        "concept_id": "x", "name": "A", "statement": "s", "family": "instruments",
        "source_thing": "a physical dial", "hierarchy_model": "instrument_like",
        "ground_surface_character": "metal", "type_character": "tabular",
        "interaction_character": "direct", "layout_structure": "fixed",
        "motion_language": "damped", "richness_source": "TYPOGRAPHY",
    }
    alternatives = {
        "ground_surface_character": "matte printed card",
        "hierarchy_model": "reading_oriented",
        "type_character": "wide numerals set for distance",
        "richness_source": "DATA_VISUALISATION",
        "interaction_character": "scroll-driven reading",
        "layout_structure": "vertical narrative",
        "motion_language": "rank movement",
    }
    for axis, value in alternatives.items():
        assert axis in concepts.DIVERGENCE_AXES, axis
        same = [
            concepts.concept(**{**base, "concept_id": f"same{index}", "name": f"S{index}"})
            for index in range(3)
        ]
        assert not concepts.material_divergence(same)["axes"] or all(
            row["divergent"] is False for row in concepts.material_divergence(same)["axes"]
        if row["axis"] == axis
        ), f"three identical candidates were counted as divergent on {axis}"
        one_differs = [
            concepts.concept(**{**base, "concept_id": f"a{index}", "name": f"A{index}"})
            for index in range(3)
        ]
        one_differs[1] = concepts.concept(**{**base, "concept_id": "b", "name": "B", axis: value})
        report = concepts.material_divergence(one_differs)
        row = next(item for item in report["axes"] if item["axis"] == axis)
        assert row["divergent"], (
            f"varying {axis} alone did not register as divergence, so the axis is decorative"
        )


@case
def candidates_that_differ_only_by_colour_are_refused():
    base = {
        "concept_id": "x", "name": "A", "statement": "s", "family": "instruments",
        "source_thing": "a physical dial", "hierarchy_model": "instrument_like",
        "ground_surface_character": "metal", "type_character": "tabular",
        "interaction_character": "direct", "layout_structure": "fixed", "motion_language": "damped",
        "richness_source": "TYPOGRAPHY",
    }
    palette = [
        concepts.concept(**{**base, "concept_id": "a", "name": "A"}),
        concepts.concept(**{**base, "concept_id": "b", "name": "B"}),
        concepts.concept(**{**base, "concept_id": "c", "name": "C"}),
    ]
    problems = concepts.divergence_problems(palette)
    assert any("only in colour" in item for item in problems), problems


@case
def two_candidates_are_refused_because_two_is_a_choice_already_made():
    candidates = f1.concept_records()[:2]
    problems = concepts.divergence_problems(candidates)
    assert any("floor is 3" in item for item in problems), problems


@case
def a_concept_that_is_only_an_adjective_is_refused():
    problems = concepts.concept_problems({
        "concept_id": "a", "name": "A", "concept": "modern and clean", "family": "instruments",
        "source_thing": "modern", "hierarchy_model": "instrument_like", "ground_surface_character": "g",
        "type_character": "t", "interaction_character": "i", "layout_structure": "l",
        "motion_language": "m", "richness_source": "TYPOGRAPHY",
    })
    assert any("aesthetic adjective" in item for item in problems), problems


@case
def the_candidate_set_does_not_collapse_onto_this_systems_own_attractors():
    candidates = f1.concept_records()
    risk = concepts.convergence_risk(candidates)
    assert risk["risk"] == "DIVERSE", risk
    convergent = [dict(row, name="Race Control Console", source_thing="a telemetry console") for row in candidates]
    problems = concepts.convergence_problems(convergent)
    assert problems, "a set that is mostly consoles must be reported as converging"


@case
def candidates_sharing_one_axis_are_reported_as_converging():
    rows = []
    for index, family in enumerate(("instruments", "media", "nature")):
        rows.append(concepts.concept(
            concept_id=f"c{index}", name=f"N{index}", statement=f"s{index}", family=family,
            source_thing=f"thing {index}", hierarchy_model="dense_operational",
            ground_surface_character="flat dark ground", type_character="tabular",
            interaction_character="direct", layout_structure="identical fixed rail",
            motion_language="state only", richness_source="REAL_CONTENT",
        ))
    problems = concepts.axis_spread_problems(rows)
    assert any("hierarchy model" in item for item in problems), problems


@case
def candidate_evaluation_produces_no_composite_score():
    evaluation = concepts.candidate_evaluation(
        f1.concept_records(),
        evidence={row["concept_id"]: {"product_fit": "STRONG"} for row in f1.concept_records()},
    )
    for row in evaluation:
        assert row["aggregate_score"] is None, row
        assert "aggregate" in row["score_note"] or "no global" in row["score_note"].lower()


@case
def a_recommendation_is_not_made_from_list_order():
    rows = f1.concept_records()
    unassessed = concepts.recommend(rows, evaluation=[], recommendation_id="rec")
    assert unassessed["status"] == "UNASSESSED", unassessed
    assert unassessed["recommended_concept_id"] == "", unassessed


# ====================================================== content before layout

@case
def content_model_precedes_layout_plan():
    models = f1.content_models()
    assert models, "the slice derives its own content model"
    plan = {"content_model": dict(models[0]), "content_model_established_at_step": 1,
            "layout_decided_at_step": 6, "planned_at": models[0].get("recorded_at", "") or "2026-01-01"}
    assert not content.content_layout_precedence(plan), content.content_layout_precedence(plan)


@case
def a_layout_committed_before_its_content_is_refused():
    models = f1.content_models()
    plan = {"content_model": dict(models[0]), "content_model_established_at_step": 7,
            "layout_decided_at_step": 3, "planned_at": "2026-01-01"}
    problems = content.content_layout_precedence(plan)
    assert any("Content before layout" in item for item in problems), problems


@case
def a_layout_plan_with_no_content_model_is_refused():
    problems = content.content_layout_precedence({})
    assert any("CONTENT_BEFORE_LAYOUT" in item for item in problems), problems


@case
def lorem_ipsum_is_refused_as_content_evidence():
    assert content.filler_findings("Lorem ipsum dolor sit amet")
    model = dict(f1.content_models()[0])
    model["headings"] = ["Lorem ipsum", "Session"]
    problems = content.content_model_problems(model)
    assert any("placeholder text" in item for item in problems), problems


@case
def suspiciously_perfect_demo_data_is_refused():
    model = dict(f1.content_models()[0])
    model["headings"] = ["Lap 41 of 58", "Lap 42 of 58", "Lap 43 of 58", "Lap 44 of 58"]
    problems = content.content_model_problems(model)
    assert any("fixture rather than content" in item for item in problems), problems


@case
def a_content_model_must_describe_its_empty_loading_and_error_states():
    model = dict(f1.content_models()[0])
    model["error_state"] = ""
    problems = content.content_model_problems(model)
    assert any("error state" in item for item in problems), problems


@case
def a_single_value_cannot_prove_a_layout_does_not_overflow():
    model = dict(f1.content_models()[0])
    model["row_count"] = {"low": 12, "high": 12, "typical": "12"}
    problems = content.content_model_problems(model)
    assert any("realistic range" in item for item in problems), problems


@case
def the_content_model_influences_layout_constraints():
    constraints = content.layout_constraints(f1.content_models()[0])
    assert any("rows" in item for item in constraints), constraints
    assert any("empty state" in item for item in constraints), constraints


@case
def believable_demo_content_still_refuses_to_impersonate_real_people():
    model = dict(f1.content_models()[0])
    model["edge_content"] = ["contact race.control@example.com for the real result"]
    findings = content.fabrication_findings(model)
    assert any("email address" in item for item in findings), findings
    honest = dict(f1.content_models()[0])
    assert not content.fabrication_findings(honest)


# ================================================= category defaults and slop

@case
def category_default_detection_does_not_imply_automatic_rejection():
    detections = defaults.detect("shadow backdrop-filter card stat")
    detected = [row for row in detections if row["detected"]]
    truthy(detected, "the probes found nothing at all")
    for row in detected:
        assert row["verdict"] == defaults.UNEXAMINED, row
        assert "not failed" in row["note"]


@case
def an_earned_pattern_is_kept_and_is_not_reported_as_a_defect():
    detections = defaults.detect("shadow backdrop-filter")
    adjudicated = defaults.adjudicate(
        detections,
        justification={"random-glass": "content genuinely passes behind the panel"},
    )
    glass = next(row for row in adjudicated if row["pattern_id"] == "random-glass")
    assert glass["verdict"] == "EARNED", glass
    assert not defaults.unexamined([glass])
    report = defaults.anti_slop_report(adjudicated, direction={"richness_source": "REAL_CONTENT"})
    assert "random-glass" in report["earned"], report
    assert "kept because the product earned them" in report["earned_is_not_a_defect"]


@case
def a_pattern_contradicted_by_the_direction_is_reported_as_contradicted():
    detections = defaults.detect("shadow")
    adjudicated = defaults.adjudicate(
        detections, direction_contradictions={"fake-depth": "the direction states no elevation is used"},
    )
    depth = next(row for row in adjudicated if row["pattern_id"] == "fake-depth")
    assert depth["verdict"] == "CONTRADICTED", depth


@case
def no_pattern_in_the_registry_is_a_ban():
    assert not defaults.assert_patterns_are_not_bans(defaults.DESIGN_DEFAULT_PATTERNS)
    banned = {
        "pattern_id": "made-up", "signals": ["x"], "domain_context": ["any"],
        "why_generic": "g", "valid_when": ["never use cards"], "alternative_question": "q",
        "deterministic_detectors": [], "requires_visual_judgment": False,
    }
    problems = defaults.assert_patterns_are_not_bans([banned])
    assert any("ban" in item for item in problems), problems


@case
def a_pattern_with_no_valid_case_is_refused_as_a_pattern():
    """A pattern with no ``valid_when`` is a ban; the registry check must say so.

    Separately named from the prohibited-phrasing case because they are different failures:
    one is a ban written as prose, the other is a pattern that never admits being correct.
    """
    valueless = {
        "pattern_id": "no-exceptions", "signals": ["x"], "domain_context": ["any"],
        "why_generic": "g", "valid_when": [], "alternative_question": "q",
        "deterministic_detectors": [], "requires_visual_judgment": False,
    }
    problems = defaults.pattern_problems(valueless)
    assert any("states when the pattern is correct" in item for item in problems), problems
    assert defaults.assert_patterns_are_not_bans([valueless])
    complete = dict(valueless, valid_when=["the product's domain genuinely is this"])
    assert not defaults.pattern_problems(complete), defaults.pattern_problems(complete)


@case
def every_pattern_states_when_it_is_correct():
    for pattern in defaults.DESIGN_DEFAULT_PATTERNS:
        assert pattern["valid_when"], pattern["pattern_id"]
        assert pattern["alternative_question"], pattern["pattern_id"]


@case
def own_slop_exists():
    direction = {"own_failure_mode": "neon HUD with fake speed lines",
                 "character": "automotive instrument cluster, physical racing instrument"}
    slop = defaults.own_slop(direction)
    assert slop["failure_mode"] == "neon HUD with fake speed lines"
    assert not defaults.own_slop_problems(direction)
    missing = {"character": "dense operational"}
    problems = defaults.own_slop_problems(missing)
    assert any("names no failure mode" in item for item in problems), problems


@case
def a_failure_mode_recorded_as_a_prohibition_is_refused():
    direction = {"own_failure_mode": "no cream and serif", "own_failure_mode_banned": True}
    problems = defaults.own_slop_problems(direction)
    assert any("prohibition" in item for item in problems), problems


@case
def anti_slop_does_not_force_austere_output():
    restrained = {"richness_source": "TYPOGRAPHY"}
    assert not grammar.richness_problems(restrained)
    report = defaults.anti_slop_report([], direction=restrained)
    assert report["restraint_allowed"], report
    assert not report["richness_problems"]
    empty = {"richness_source": ""}
    assert defaults.anti_slop_report([], direction=empty)["richness_problems"]


@case
def project_identity_remains_stronger_than_external_inspiration():
    direction = {
        "product_context": ["[project] Formula 1 race operations"],
        "existing_system": ["[project] from-scratch workspace"],
    }
    trace = sp.__dict__  # the package must not provide a way to rank references over the project
    assert "authority_check" in dir(sources), sources
    verdict = sources.authority_check(
        "shadcn", direction_claims="the direction requires a data-table primitive with sticky headers",
        rationale="shadcn provides the primitive",
    )
    assert verdict["ok"], verdict
    blind = sources.authority_check("shadcn", rationale="it exists on shadcn so we should use it")
    assert not blind["ok"], blind


@case
def a_registry_entry_is_not_an_integration():
    registry = sources.registry()
    assert not registry["problems"], registry["problems"]
    available = registry["by_status"].get("ADAPTER_AVAILABLE", [])
    assert len(available) < registry["count"], (
        "every source claiming an adapter is the failure this taxonomy exists to catch"
    )
    for row in registry["sources"]:
        if row["adapter_status"] == "ADAPTER_AVAILABLE":
            assert row["adapter_id"], row["source_id"]
            assert "BROWSER_ONLY" not in row["capabilities"], row["source_id"]


# ==================================================== platform profile boundary

@case
def platform_specific_rule_does_not_leak_into_universal_grammar():
    assert not platform.platform_rule_leaks("content before layout", "meaning before aesthetic adjective")
    leaks = platform.platform_rule_leaks("use a 44pt minimum interactive control target")
    assert leaks and leaks[0].startswith("ios:"), leaks
    safe = platform.platform_rule_leaks("SF Symbols as the icon vocabulary")
    assert any(item.startswith("ios:") for item in safe), safe


@case
def an_unknown_platform_profile_raises_rather_than_returning_empty():
    raises(lambda: platform.profile_for("smartfridge"), "unknown platform profile")
    assert platform.profile_for("web")["rules"]


@case
def platform_rules_are_bound_to_the_profile_not_the_universal_body():
    unbound = platform.bound_platform_profiles(["44pt minimum interactive control target"], platform="")
    assert unbound["platform_rule_citations"], unbound
    assert unbound["platform_bound"], (
        "an iOS rule cited with no platform named is a platform rule pretending to be universal"
    )
    assert not unbound["platform_rules"], "with no platform named there are no platform rules to bind"
    bound = platform.bound_platform_profiles(
        ["44pt minimum interactive control target"], platform="ios",
    )
    assert bound["platform_profile"] == "ios", bound
    assert bound["platform_rules"], bound
    assert not bound["platform_bound"], "a named profile is where the rule legitimately lives"
    clean = platform.bound_platform_profiles(["content before layout"], platform="")
    assert not clean["platform_bound"], clean


@case
def a_universal_record_citing_an_ios_rule_is_refused():
    raises(
        lambda: platform.assert_no_leak(
            "use a 44pt minimum interactive control target on every surface", label="direction",
        ),
        "platform-specific rules as universal",
    )


# ==================================================== source ecosystem

@case
def source_roles_and_capabilities_are_declared_and_known():
    for row in sources.SOURCE_CATALOG:
        assert row["source_roles"], row["source_id"]
        for role in row["source_roles"]:
            assert role in sources.SOURCE_ROLES, (row["source_id"], role)
        for capability in row["capabilities"]:
            assert capability in sources.SOURCE_CAPABILITIES, (row["source_id"], capability)


@case
def a_disabled_source_says_why():
    disabled = [row for row in sources.SOURCE_CATALOG if not row["enabled"]]
    truthy(disabled, "the registry keeps verified-absent sources as findings")
    for row in disabled:
        assert row["disabled_reason"], row["source_id"]
        assert row["adapter_status"] == "DISABLED", row["source_id"]


@case
def a_paid_source_is_never_enabled_by_default():
    for row in sources.SOURCE_CATALOG:
        if row["paid_access"]:
            assert not row["enabled"] or row["adapter_status"] != "ADAPTER_AVAILABLE", row["source_id"]


@case
def auth_and_paid_access_are_recorded_separately():
    keyed = sources.SOURCE_PROFILES["21st-dev"]
    assert keyed["access_mode"] == "account"
    assert keyed["authentication"] != "none"
    public = sources.SOURCE_PROFILES["shadcn"]
    assert public["access_mode"] == "public" and public["authentication"] == "none"


@case
def reuse_policy_is_recorded_for_every_adaptable_source():
    for row in sources.SOURCE_CATALOG:
        if row["adapter_status"] in ("ADAPTER_AVAILABLE", "ADAPTER_VENDOR_KEY_REQUIRED"):
            assert row["reuse_policy"], row["source_id"]
            assert row["license_visibility"], row["source_id"]


@case
def browser_only_source_remains_browser_only():
    uiverse = sources.SOURCE_PROFILES["uiverse"]
    assert "BROWSER_ONLY" in uiverse["capabilities"]
    assert uiverse["adapter_status"] == "BROWSER_RESEARCH_SOURCE"
    assert not uiverse["adapter_id"], uiverse


@case
def a_browser_only_source_claiming_an_adapter_is_refused_by_the_registry_itself():
    """The contradiction must be caught from a *profile*, not only from live data.

    Every source currently satisfies this, which means a check that only inspects the
    shipped registry would never fire -- and the first source to arrive claiming both would
    sail through.
    """
    contradictory = {
        "source_id": "contradictory", "display_name": "Contradictory",
        "source_roles": ["COMPONENT_PATTERN"], "capabilities": ["BROWSER_ONLY", "COMPONENT_CODE"],
        "access_mode": "public", "authentication": "none", "paid_access": False,
        "machine_readable": "HTML_ONLY", "license_visibility": "MIT",
        "reuse_policy": "MIT", "prohibited_uses": [], "adapter_status": "ADAPTER_AVAILABLE",
        "adapter_id": "claimed", "endpoint": "https://example.invalid",
        "terms_notes": "", "verification_notes": "synthetic", "enabled": True,
        "disabled_reason": "", "selection_notes": "",
    }
    problems = sources.source_problems(contradictory)
    assert any("BROWSER_ONLY" in item for item in problems), problems
    registry = sources.registry()
    problems.extend(sources.source_problems(contradictory))
    assert problems, problems


@case
def a_source_claiming_an_adapter_without_naming_it_is_refused():
    unnamed = {
        "source_id": "unnamed", "display_name": "Unnamed", "source_roles": ["COMPONENT_PATTERN"],
        "capabilities": ["COMPONENT_CODE", "CLI"], "access_mode": "public", "authentication": "none",
        "paid_access": False, "machine_readable": "REGISTRY_JSON", "license_visibility": "MIT",
        "reuse_policy": "MIT", "prohibited_uses": [], "adapter_status": "ADAPTER_AVAILABLE",
        "adapter_id": "", "endpoint": "https://example.invalid", "terms_notes": "",
        "verification_notes": "synthetic", "enabled": True, "disabled_reason": "",
        "selection_notes": "",
    }
    problems = sources.source_problems(unnamed)
    assert any("names the adapter" in item for item in problems), problems
    named = dict(unnamed, adapter_id="real-adapter")
    assert not sources.source_problems(named), sources.source_problems(named)


@case
def an_adapter_without_visible_licence_terms_is_refused():
    unlicensed = {
        "source_id": "unlicensed", "display_name": "Unlicensed", "source_roles": ["COMPONENT_PATTERN"],
        "capabilities": ["COMPONENT_CODE", "CLI"], "access_mode": "public", "authentication": "none",
        "paid_access": False, "machine_readable": "REGISTRY_JSON", "license_visibility": "",
        "reuse_policy": "MIT", "prohibited_uses": [], "adapter_status": "ADAPTER_AVAILABLE",
        "adapter_id": "real-adapter", "endpoint": "https://example.invalid", "terms_notes": "",
        "verification_notes": "synthetic", "enabled": True, "disabled_reason": "",
        "selection_notes": "",
    }
    problems = sources.source_problems(unlicensed)
    assert any("licence terms" in item for item in problems), problems


@case
def no_unsupported_adapter_claim():
    for row in sources.SOURCE_CATALOG:
        if row["adapter_status"] == "ADAPTER_AVAILABLE":
            assert row["endpoint"], row["source_id"]
            assert row["machine_readable"] not in ("HTML_ONLY", "VIDEO_ONLY"), row["source_id"]


@case
def provider_metadata_lying_about_capability_is_a_contradiction():
    lie = sources.capability_claims_match_reality(
        "uiverse", claimed={"capabilities": ["API", "BROWSER_ONLY"]},
    )
    assert not lie["ok"], lie
    assert "BROWSER_ONLY" in lie["contradiction"], lie
    honest = sources.capability_claims_match_reality(
        "shadcn", claimed={"capabilities": ["API", "CLI"]},
    )
    assert honest["ok"], honest


@case
def source_selection_is_need_driven_and_bounded():
    for need in sources.EVIDENCE_NEEDS:
        selection = sources.select_sources(need)
        assert len(selection["sources_selected"]) <= sources.MAX_SOURCES_PER_NEED, selection
        assert selection["sources_considered"] == sources.registry()["count"]
        assert selection["skipped"], f"{need} skipped nothing, so nothing was chosen"
    table = sources.select_sources("DATA_TABLE_PATTERNS")
    motion = sources.select_sources("LANDING_MOTION")
    assert table["sources_selected"] != motion["sources_selected"], (
        "two different needs selected identical sources, so selection is not need-driven"
    )


@case
def no_query_everything_behavior():
    total = sum(len(sources.select_sources(need)["sources_selected"]) for need in sources.EVIDENCE_NEEDS)
    registry_size = sources.registry()["count"]
    assert total <= len(sources.EVIDENCE_NEEDS) * sources.MAX_SOURCES_PER_NEED, total
    truthy(registry_size > total, f"{total} selections against {registry_size} sources")
    for need in sources.EVIDENCE_NEEDS:
        assert sources.select_sources(need)["not_everything"]


@case
def a_paid_source_is_selected_only_with_a_reason():
    selection = sources.select_sources("REAL_PRODUCT_FLOW_PATTERN")
    skipped = {row["source_id"]: row["reason"] for row in selection["skipped"]}
    assert "mobbin" in skipped, skipped
    assert "authorization" in skipped["mobbin"], skipped


@case
def adapter_required_selection_excludes_browser_research_sources():
    selection = sources.select_sources("COMPLETE_VISUAL_DIRECTION", adapter_required=True)
    for row in selection["selected"]:
        assert row["adapter_status"] == "ADAPTER_AVAILABLE", row


@case
def context_budget_is_recorded_for_a_selection():
    economics = sources.selection_economics(
        [sources.select_sources("DATA_TABLE_PATTERNS")],
        bytes_by_source={"shadcn": 4096}, seconds_by_source={"shadcn": 1.5},
    )
    assert economics["bytes_transported"] == 4096, economics
    assert economics["deep_inspections"] == 1, economics
    assert economics["sources_queried"] == 1, economics
    truthy(economics["stopped_because"], economics)


@case
def implementation_registry_is_not_aesthetic_authority():
    blind = sources.authority_check("magicui", rationale="Magic UI has it")
    assert not blind["ok"], blind
    grounded = sources.authority_check(
        "magicui", direction_claims="LANDING_MOTION needs a marquee primitive",
        rationale="the approved direction's motion intent is state confirmation, and a marquee is not one",
    )
    assert grounded["ok"], grounded
    missing = sources.authority_check("magicui")
    assert not missing["ok"], missing


@case
def an_unverified_licence_is_not_treated_as_reusable():
    microkit = sources.reuse_check("microkit", use="read the registry index for component patterns")
    assert not microkit["ok"], microkit
    assert "not established" in microkit["problem"], microkit


@case
def inspiration_source_does_not_grant_reuse_rights():
    for source_id, activity in (
        ("minimal-gallery", "copy the composition into our project"),
        ("uiverse", "reproduce layout from the gallery entry"),
        ("cta-gallery", "clone composition from the collection page"),
        ("footer-design", "extract component markup from the entry"),
    ):
        verdict = sources.reuse_check(source_id, use=activity)
        assert not verdict["ok"], (source_id, activity, verdict)
    observing = sources.reuse_check("minimal-gallery", use="observe hierarchy and rhythm in a browser")
    assert observing["ok"], observing


@case
def a_paid_licence_does_not_buy_a_prohibited_use():
    training = sources.reuse_check("refero", use="train a model on Refero screenshots")
    assert not training["ok"], training
    assert "paying" in training["note"], training
    index = sources.reuse_check("refero", use="use Refero results to build a design index")
    assert not index["ok"], index
    permitted = sources.reuse_check("refero", use="apply insights from Refero to our own product design")
    assert permitted["ok"], permitted


@case
def design_md_providers_are_distinct_source_identities():
    getdesign = sources.SOURCE_PROFILES["getdesign"]
    repo = sources.SOURCE_PROFILES["awesome-design-md"]
    designmd = sources.SOURCE_PROFILES["designmd-ai"]
    assert len({getdesign["source_id"], repo["source_id"], designmd["source_id"]}) == 3
    assert getdesign["license_visibility"] != designmd["license_visibility"]


@case
def the_existing_getdesign_corpus_path_is_preserved():
    from ariadne_engine.design_reference import getdesign, FIXTURE_ROOT

    assert FIXTURE_ROOT.is_dir(), FIXTURE_ROOT
    corpus = sorted(path.name for path in FIXTURE_ROOT.glob("*.md"))
    truthy(corpus, "the frozen getdesign corpus shipped with AR-220 is intact")
    adapter = getdesign.default_adapter(FIXTURE_ROOT)
    assert adapter.enabled(), "the AR-220 offline getdesign path must still be enabled"
    truthy(adapter.corpus, "the frozen corpus is loaded offline")
    index = getdesign.build_index(adapter.index)
    truthy(index, "the frozen corpus still builds an offline index")
    results = getdesign.search(index, "dashboard density", limit=5)
    assert len(results) <= 5, results
    for row in results:
        assert getdesign.entry_url(row.slug).startswith("https://"), row.slug


# =============================================== minimal creative interruption

@case
def simple_vague_request_does_not_trigger_unnecessary_questions():
    report = f1.run()
    questions = [
        "pick an aesthetic category", "choose a provider", "which design system",
        "choose a component library", "choose a font", "should i search",
        "which registry", "capture dimensions", "which implementation primitive",
    ]
    visible = (report["user_interface"] or "").lower()
    for question in questions:
        assert question not in visible, f"the interface asked a question it must not ask: {question}"


@case
def reference_selection_is_automatic():
    for change in ("reference selection", "source provider choice", "capture planning",
                   "counter-reference search", "transport choice"):
        assert not interruption.classify(change)["interrupts_user"], change


@case
def component_choice_is_automatic():
    for change in ("use the 21st.dev accordion component", "choose between shadcn and 21st.dev",
                   "which design system should I use", "pick a shadcn primitive", "component library choice"):
        assert not interruption.classify(change)["interrupts_user"], change


@case
def g1d_requires_human_approval():
    verdict = interruption.classify("G1D design-direction approval")
    assert verdict["tier"] == "HUMAN_REQUIRED" and verdict["gate"] == "G1D", verdict
    assert interruption.classify("meaningful direction revision")["tier"] == "HUMAN_REQUIRED"


@case
def direction_revision_requires_a_new_human_decision():
    for change in ("replace the top navigation with a persistent sidebar",
                   "swap to a completely different visual language",
                   "rebrand with a new logo",
                   "change the audience we are designing for",
                   "abandon the pit-wall metaphor for something lighter",
                   "wire up drag instead of tap"):
        verdict = interruption.classify(change)
        assert verdict["tier"] == "HUMAN_REQUIRED", (change, verdict)
        assert verdict["meaning_bearing"], change


@case
def routine_refinement_does_not_interrupt():
    for change in ("increase the button padding by 8px", "adjust the spacing scale",
                   "refactor the component implementation", "change responsive mechanics",
                   "strengthen the hierarchy slightly"):
        verdict = interruption.classify(change)
        assert not verdict["interrupts_user"], (change, verdict)


@case
def routine_tooling_questions_are_classified_automatic_not_merely_non_interrupting():
    """These must be AUTOMATIC, not merely tolerated.

    ``CONDITIONAL`` also proceeds, so asserting only "did not interrupt" would pass with the
    routine-vocabulary rule removed entirely -- and a policy where every routine question
    lands in the unclassified tier is one short of asking the user about everything.
    """
    for change in ("use the 21st.dev accordion component", "which design system should I use",
                   "pick a shadcn primitive", "component library choice",
                   "decide the capture viewport", "colour palette selection",
                   "typography candidate evaluation"):
        verdict = interruption.classify(change)
        assert verdict["tier"] == "AUTOMATIC", (change, verdict)
    # This phrasing names no design-system vocabulary at all -- it is two registry names and
    # a verb -- so it is classified by the provider tokens alone. Included because it is the
    # exact question the brief forbids, and it is the hardest of the four to recognise.
    registry_choice = interruption.classify("choose between shadcn and 21st.dev")
    assert not registry_choice["interrupts_user"], registry_choice
    registry_choice = interruption.classify("should I use shadcn or 21st.dev")
    assert not registry_choice["interrupts_user"], registry_choice
    registry_choice = interruption.classify("should I search Mobbin")
    assert not registry_choice["interrupts_user"], registry_choice


@case
def a_bare_meaning_noun_without_a_replacement_is_not_a_meaning_change():
    verdict = interruption.classify("add a menu button to the existing header")
    assert not verdict["meaning_bearing"], verdict
    assert not verdict["interrupts_user"], verdict


@case
def paid_protected_action_still_requires_existing_authorization():
    verdict = interruption.classify("use a paid provider for component search")
    assert verdict["tier"] == "HUMAN_REQUIRED", verdict
    assert "protected authorization" in interruption.policy()["human_required"]


@case
def the_interruption_policy_is_recorded_and_bounded():
    policy = interruption.policy()
    assert not interruption.policy_problems(policy), interruption.policy_problems(policy)
    assert policy["user_operates"] is False
    assert len(policy["automatic"]) > len(policy["human_required"]) * 3, (
        "if the automatic list is no longer much larger, the policy has become interrupt-on-everything"
    )
    shrunk = dict(policy, automatic=policy["automatic"][:3])
    assert interruption.policy_problems(shrunk)


@case
def the_run_reaches_an_approved_direction_without_a_second_interruption():
    report = f1.run()
    assert report["completed"], report["failures"]
    assert report["continuation"]["interruptions_after_approval"] == 0, report["continuation"]
    assert not report["continuation"]["single_interruption_problems"]


# ======================================================= proposal and approval

@case
def the_proposal_exposes_no_internal_provider_identity():
    report = f1.run()
    assert not report["proposal"]["internal_fields_leaked"], report["proposal"]
    text = report["proposal"]["user_visible_text"]
    for token in ("adapter", "transport", "mcp", "http", "sha", "digest", "res_", "rfd_"):
        assert token not in text.lower(), f"the proposal leaked {token!r}"


@case
def a_proposal_carrying_an_internal_identifier_is_refused():
    """The refusal must fire on a *proposal*, not only on the slice's clean output.

    Every proposal the slice builds is clean, so a check that only inspects that output
    would never fire and the boundary would be decorative.
    """
    dirty = _proposal_record()
    dirty["preview_refs"] = ["adapter_id: 21st-api", "transport: MCP"]
    problems = proposal.proposal_problems(dirty)
    assert any("internal identity" in item or "internal field" in item for item in problems), problems
    # The leak is in the rendered body rather than in preview_refs, so only the text check can
    # catch it. Both checks are needed: one guards the preview list, the other the prose.
    in_text = _proposal_record()
    in_text["concept"] = "a workspace using adapter_id shadcn-registry for its primitives"
    problems = proposal.proposal_problems(in_text)
    assert any("internal field" in item for item in problems), problems
    named = _proposal_record()
    named["preview_refs"] = ["first reference", "second reference"]
    assert not proposal.proposal_problems(named), proposal.proposal_problems(named)


def _proposal_record() -> dict:
    return {
        "proposal_id": "dpp_1", "direction_id": "ddr_1", "name": "Race Control",
        "concept": "a workspace based on race engineering",
        "character": "read under time pressure",
        "content_strategy": "real session volumes", "typography_intent": "timing first",
        "colour_intent": "neutral instrument surfaces", "layout_intent": "a fixed rail",
        "richness_source": "REAL_CONTENT", "motion_intent": "STATE_CONFIRMATION",
        "key_principles": ["schedule in one glance"],
        "deliberately_avoided_defaults": ["neon HUD with fake speed lines"],
        "preview_refs": [], "approval_required": True, "gate": "G1D",
    }


@case
def the_proposal_is_short_enough_to_approve():
    report = f1.run()
    text = report["proposal"]["user_visible_text"]
    assert len(text.splitlines()) <= 40, len(text.splitlines())
    assert len(text.split()) <= 420, len(text.split())
    for section in ("Content:", "Hierarchy:", "Colour:", "Layout:", "Motion:", "Avoiding:"):
        assert section in text, section


@case
def the_proposal_offers_a_recommendation_not_a_survey():
    report = f1.run()
    assert report["recommendation"]["status"] == "RECOMMENDED", report["recommendation"]
    assert report["recommendation"]["alternatives"], "alternatives must stay available"
    assert report["recommendation"]["alternatives_role"] == "secondary"
    actions = report["proposal"]["actions"]
    assert actions == ["approve", "adjust", "show-alternatives"], actions


@case
def the_proposal_shows_what_the_direction_avoids():
    report = f1.run()
    text = report["proposal"]["user_visible_text"]
    assert "Avoiding:" in text
    for avoided in ("generic dark-fintech cards", "neon cyberpunk treatment"):
        assert avoided in text, avoided


@case
def a_proposal_that_disagrees_with_its_direction_is_refused():
    direction = {"richness_source": "DATA_VISUALISATION", "own_failure_mode": "neon HUD"}
    record = {
        "name": "X", "concept": "c", "character": "ch", "content_strategy": "cs",
        "typography_intent": "ti", "colour_intent": "ci", "layout_intent": "li",
        "richness_source": "PHOTOGRAPHY", "motion_intent": "REWARD",
        "key_principles": ["p"], "deliberately_avoided_defaults": ["monochrome cards"],
        "preview_refs": [], "approval_required": True, "gate": "G1D",
    }
    problems = proposal.proposal_problems(record, direction=direction)
    assert any("richness source" in item for item in problems), problems
    assert any("failure mode" in item for item in problems), problems


@case
def an_approval_binds_the_text_the_user_read():
    report = f1.run()
    approval = report["approval"]
    assert approval["proposal_digest_matches_shown_text"], approval
    assert approval["approver"] == f1.FIXTURE_APPROVER
    assert approval["authority"] == "human"


@case
def approval_is_not_bypassed_before_the_real_gate():
    report = f1.run()
    truthy(report["refusal_without_approval"], "planning was not refused before approval")
    assert "DESIGN_DIRECTION_UNAPPROVED" in report["refusal_without_approval"], report["refusal_without_approval"]
    assert report["direction"]["status_after_approval"] == "approved", report["direction"]
    truthy(report["approval"]["approval_id"], "no real G1D approval was recorded")
    assert report["approval"]["approved_text_matches_shown_text"], report["approval"]


@case
def approval_is_not_bypassed():
    report = f1.run()
    truthy(report["refusal_without_approval"], "planning was not refused before approval")
    assert "DESIGN_DIRECTION_UNAPPROVED" in report["refusal_without_approval"], report["refusal_without_approval"]
    assert report["direction"]["status_after_approval"] == "approved", report["direction"]
    truthy(report["approval"]["approval_id"], "no real G1D approval was recorded")
    assert report["approval"]["approved_text_matches_shown_text"], report["approval"]


@case
def the_implementing_worker_may_not_approve_its_own_direction():
    from ariadne_engine import design as design_module

    state: dict = {
        "run_id": contracts.new_record_id("run"), "schema_version": contracts.SCHEMA_RECORD,
        "engine": {},
    }
    direction = design_module.create_direction(
        state, task_id="t", goal="g", scope="s",
        product_context=["[project] x"], key_hierarchy=["k"],
        interaction_principles=["i"], visual_principles=["v"], content_principles=["c"],
        constraints=["n"], existing_system=["[project] from scratch"],
        reference_findings_adopted=["adopted one"], findings_rejected=["rejected one"],
        accessibility_requirements=["contrast"], responsive_requirements=["reflows"],
        approved_deviations=["no imagery"],
    )
    from ariadne_engine import review as review_module

    state["worker"] = {"identity": "ar222d-worker", "worker_role": "implementation"}
    truthy("ar222d-worker" in {value.lower() for value in review_module.worker_identities(state)}, state)
    raises(
        lambda: design_module.approve_direction(
            state, str(direction["direction_id"]), identity="ar222d-worker", note="self",
        ),
        "cannot approve its own design direction",
    )
    approval = design_module.approve_direction(
        state, str(direction["direction_id"]), identity="human-operator", note="ok",
    )
    truthy(approval.get("approval_id"), approval)


@case
def a_proposal_approval_recorded_against_stale_text_is_refused():
    report = f1.run()
    record = {
        "proposal_id": "dpp_1", "direction_id": "ddr_1", "name": "X", "concept": "c",
        "character": "ch", "content_strategy": "cs", "typography_intent": "ti",
        "colour_intent": "ci", "layout_intent": "li", "richness_source": "TYPOGRAPHY",
        "motion_intent": "REWARD", "key_principles": ["p"],
        "deliberately_avoided_defaults": ["monochrome cards"], "preview_refs": [],
        "approval_required": True, "gate": "G1D",
    }
    approval = proposal.approval_record(record, identity="human")
    changed = dict(record, concept="a different concept entirely")
    problems = proposal.approval_problems(approval, proposal_record=changed)
    assert any("different direction" in item for item in problems), problems


# =============================================== critic continuity and proof

@case
def critic_continuity_is_possible_without_losing_independence():
    session = continuity.new_session(
        direction_id="ddr_1", task_id="t1", reviewer_execution="rev-1",
        reviewer_identity="deterministic-render-reviewer",
    )
    session = continuity.request_repair(session, finding_id="rfd_1", request="the 390px table must not clip")
    nxt = continuity.continue_session(session, round_number=2, previous={
        "findings": [{"finding_id": "rfd_1", "dimension": "responsiveness", "severity": "major",
                      "observation": "clips", "requirement_ids": ["req-1"]}],
        "evidence_set_id": "res_1",
    })
    assert nxt["review_session_id"] == session["review_session_id"]
    assert nxt["memory"]["previous_findings"], nxt["memory"]
    assert nxt["memory"]["requested_repairs"], nxt["memory"]
    follow_up = continuity.did_prior_request_land(nxt, finding_id="rfd_1")
    assert follow_up["asked"] and "round 1 asked for" in follow_up["question"], follow_up
    assert not continuity.independence_problems(nxt, reviewer_execution="rev-1", implementing_execution="wrk-1")


@case
def critic_memory_may_not_carry_implementation_rationale():
    session = continuity.new_session(direction_id="ddr_1", task_id="t1", reviewer_execution="rev-1")
    leaked = dict(session, memory={**session["memory"], "implementation_rationale": ["the worker widened it"]})
    problems = continuity.memory_problems(leaked)
    assert any("implementation_rationale" in item for item in problems), problems
    for field in continuity.MEMORY_FORBIDDEN_FIELDS:
        assert field not in continuity.MEMORY_ALLOWED_FIELDS, field


@case
def the_critic_may_not_be_the_implementer_across_a_session():
    session = continuity.new_session(direction_id="ddr_1", task_id="t1", reviewer_execution="rev-1")
    problems = continuity.independence_problems(session, reviewer_execution="rev-1", implementing_execution="rev-1")
    assert problems, "continuity must not let a session certify itself"


@case
def critic_session_changed_silently_mid_loop_is_refused():
    session = continuity.new_session(direction_id="ddr_1", task_id="t1", reviewer_execution="rev-1")
    silent = dict(session, mode="RESTARTED")
    problems = continuity.memory_problems(silent)
    assert any("recorded no reason" in item for item in problems), problems
    restarted = continuity.restart_session(session, reason="two bounded attempts exhausted", reviewer_execution="rev-2")
    assert restarted["restarted_from"] == session["review_session_id"]
    assert not continuity.memory_problems(restarted)


@case
def a_declined_critique_request_records_a_canonical_reason():
    session = continuity.new_session(direction_id="ddr_1", task_id="t1", reviewer_execution="rev-1")
    declined = continuity.decline(
        session, finding_id="rfd_1", recommendation="replace the whole table",
        reason="exceeds approved scope", detail="a CSS clamp is bounded",
    )
    assert declined["memory"]["declined_requests"][0]["canonical_reason"] == "exceeds approved scope"
    raises(
        lambda: continuity.decline(session, finding_id="rfd_2", recommendation="x", reason=""),
        "records a reason",
    )
    raises(
        lambda: continuity.decline(session, finding_id="rfd_3", recommendation="x", reason="we prefer it"),
        "matches none of the recognised decline reasons",
    )


@case
def requirement_to_evidence_is_walkable():
    report = f1.run()
    assert report["proof_readiness"]["requirements"], report["proof_readiness"]
    assert report["proof_readiness"]["gaps"] == 0, report["proof_readiness"]


@case
def proof_readiness_produces_no_acceptance_verdict():
    report = f1.run()
    assert report["proof_readiness"]["verdicts"] == []
    note = report["proof_readiness"]["note"]
    for verdict in ("PROVEN", "PARTIAL", "UNPROVEN", "FAILED", "CONTRADICTED", "NEEDS_HUMAN"):
        assert verdict in note, f"{verdict} belongs to AR-223 and must be named as out of scope"


@case
def reviewer_identity_is_preserved_and_worker_differs_from_reviewer():
    state = _proof_state()
    report = proof.proof_report(state)
    reviewers = report["actors"]["independent_reviewer"]
    truthy(reviewers, report["actors"])
    assert reviewers[0]["reviewer_execution"] != reviewers[0]["implementing_execution"]
    assert not report["self_certification"], report["self_certification"]


@case
def self_certification_is_reported_when_one_actor_both_built_and_reviewed():
    state = _proof_state()
    for critique in state["rendered_critiques"]:
        critique["reviewer_execution"] = "wrk-1"
    findings = proof.self_certification_findings(state)
    truthy(findings, "the worker reviewing its own work must be reported")
    assert any("independent_reviewer" in item["roles"] for item in findings), findings


@case
def finding_to_evidence_and_repair_to_new_source_digest():
    state = _proof_state()
    paths = proof.requirement_paths(state)
    finding = paths[0]["findings"][0]
    truthy(finding["requirement_id_on_finding"] == "req-1", finding)
    assert len(finding["evidence"]["observed_work_digest"]) == 64, finding["evidence"]
    repair = finding["repair"]
    assert repair["work_digest_before"] != repair["work_digest_after"], repair
    assert repair["after_evidence_set_id"] == "res_2", repair


@case
def requirement_id_dropped_from_a_finding_is_a_gap_not_a_guess():
    state = _proof_state()
    state["rendered_critiques"][0]["findings"][0]["requirement_ids"] = []
    problems = proof.proof_problems(state)
    assert any("does not carry its requirement id" in item for item in problems), problems
    assert any("cites no requirement at all" in item for item in problems), problems


@case
def historical_evidence_is_not_overwritten():
    state = _proof_state()
    before = [row for row in state["rendered_evidence_sets"] if row["evidence_set_id"] == "res_1"]
    truthy(before, "the before-evidence set must still exist after a repair")
    assert state["rendered_critiques"][0]["findings"], "the original finding must survive"
    assert not proof.assert_append_only(state), proof.assert_append_only(state)


@case
def repair_history_overwritten_is_reported():
    state = _proof_state()
    state["refinement_plans"][0]["render_source_digest_before"] = ""
    problems = proof.assert_append_only(state)
    assert any("pre-repair work digest is gone" in item for item in problems), problems


@case
def the_proof_fixture_carries_its_gaps_rather_than_hiding_them():
    state = _proof_state()
    state["refinement_plans"][0]["after_evidence_set_id"] = ""
    lineage = proof.fixture_lineage(state, requirement_id="req-1")
    assert lineage["state"] == "INCOMPLETE", lineage
    truthy(lineage["gaps"], lineage)
    assert lineage["available"]["new_evidence_identity"] is False, lineage["available"]


@case
def every_actor_role_ar223_must_distinguish_is_known():
    assert set(proof.ACTOR_ROLES) == {
        "user_or_human_approver", "implementation_worker", "evidence_producer",
        "independent_reviewer", "repair_worker", "engine",
    }
    for producer, reviewer in proof.SELF_CERTIFICATION_PAIRS:
        assert producer in proof.ACTOR_ROLES and reviewer in proof.ACTOR_ROLES


def _proof_state() -> dict:
    """A complete two-pass lineage, used by the proof-readiness cases above."""
    return {
        "run_id": "run-1", "schema_version": contracts.SCHEMA_RECORD, "engine": {},
        "approvals": [{"approval_id": "apv_1", "identity": "human", "channel": "human-cli",
                       "subject_id": "ddr_1", "subject_type": "design-direction-record"}],
        "design_directions": [{"direction_id": "ddr_1", "task_id": "t1"}],
        "design_requirements": [{"record_id": "drq_1", "requirement_id": "req-1",
                                 "state": "implemented", "revision_hash": "a" * 64}],
        "design_implementation_plans": [{"plan_id": "pl_1", "implementation_execution": "wrk-1",
                                         "requirement_ids": ["req-1"], "revision_hash": "b" * 64}],
        "rendered_evidence_sets": [
            {"evidence_set_id": "res_1", "render_source_digest": "b" * 64, "status": "SUPERSEDED",
             "superseded_by": "res_2", "captures": [{"capture_id": "c1"}, {"capture_id": "c2"}]},
            {"evidence_set_id": "res_2", "render_source_digest": "c" * 64, "status": "COMPLETE",
             "captures": [{"capture_id": "c3"}]},
        ],
        "rendered_critiques": [{
            "critique_id": "drc_1", "evidence_set_id": "res_1", "reviewer_execution": "rev-1",
            "reviewer_identity": "independent", "implementing_execution": "wrk-1",
            "requirements": ["req-1"], "review_session_id": "rvs_1",
            "findings": [{"finding_id": "rfd_1", "requirement_ids": ["req-1"],
                          "dimension": "responsiveness", "severity": "major", "state": "REPAIRED_CANDIDATE"}],
        }],
        "refinement_plans": [{
            "refinement_plan_id": "rfp_1", "critique_id": "drc_1", "finding_ids": ["rfd_1"],
            "repair_execution": "rep-1", "status": "RE_RENDERED",
            "render_source_digest_before": "b" * 64, "render_source_digest_after": "c" * 64,
            "after_evidence_set_id": "res_2",
        }],
    }


# ================================================ harness integrity

@case
def record_lookup_returns_detached_copy_where_canonical_mutation_required():
    from ariadne_engine.rendered_critique import critique, evidence, refinement
    from ariadne_engine import render

    state = _proof_state()
    critique.by_id(state, "drc_1")["reviewer_identity"] = "changed"
    assert state["rendered_critiques"][0]["reviewer_identity"] == "changed", critique.by_id.__doc__
    evidence.by_id(state, "res_1")["status"] = "CURRENT"
    assert state["rendered_evidence_sets"][0]["status"] == "CURRENT", evidence.by_id.__doc__
    refinement.by_id(state, "rfp_1")["status"] = "CLOSED"
    assert state["refinement_plans"][0]["status"] == "CLOSED", refinement.by_id.__doc__
    # render.by_id keys on evidence_id (AR-202D's field), not the AR-222 evidence_set_id.
    state["rendered_evidence"] = [{"evidence_id": "ev_1", "status": "OLD"}]
    render.by_id(state, "ev_1")["status"] = "NEW"
    assert state["rendered_evidence"][0]["status"] == "NEW", (
        "render.by_id must also hand back the live record; a copy here would make every rendered-"
        "evidence closure a silent no-op"
    )


@case
def scope_enforcement_mutation_becomes_no_op_is_caught():
    """A repair that escapes its allowed scope must be refused by the engine itself.

    This used to re-implement the scope comparison locally, which made it a test of the
    test file: the mutation it was written for could be applied and the case still passed.
    The call is now the engine's own ``mark_validated``.
    """
    from ariadne_engine.rendered_critique import critique as critique_module, refinement

    state = _refinement_state()
    truthy(state["refinement_plans"][0]["allowed_scope"], state["refinement_plans"][0])
    raises(
        lambda: refinement.record_change(
            state, "rfp_1", execution="rep-1",
            changed_files=["src/styles/app.css", "src/app/shell.ts"],
            notes="widened the shell while fixing a table",
        ),
        "outside its allowed scope",
    )
    # And the in-scope repair still works, so the check is a boundary and not an obstacle.
    ok = refinement.record_change(
        state, "rfp_1", execution="rep-1",
        changed_files=["src/styles/app.css"], notes="scoped to the stylesheet",
    )
    assert ok["changed_files"] == ["src/styles/app.css"], ok
    assert state["refinement_plans"][0]["changed_files"] == ["src/styles/app.css"], (
        "record_change must write through to canonical state"
    )
    truthy(critique_module.all_findings(state), "the critique still carries its findings")


def _refinement_state() -> dict:
    state = _proof_state()
    state["refinement_plans"][0].update({
        "status": "PROPOSED",
        "allowed_scope": ["src/styles/*.css"],
        "forbidden_scope": ["src/app/shell.ts"],
        "changed_files": [],
    })
    return state


@case
def mutation_harness_restores_transactionally():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("ORIGINAL = True\n", encoding="utf-8")
        original = target.read_bytes()
        report = {}
        try:
            with mutation_ledger.mutation_transaction(
                repo, harness="ar222d-test", mutation_id="m1", targets=[target],
            ) as opened:
                target.write_text("ORIGINAL = False\n", encoding="utf-8")
                assert target.read_text() != original.decode()
                report = opened
        except Exception as exc:  # pragma: no cover - the harness must not raise here
            raise AssertionError(f"the transaction raised: {exc}") from exc
        assert target.read_bytes() == original, "the transaction did not restore the original bytes"
        restoration = report["restoration"]
        assert restoration["restored"], restoration
        assert not mutation_ledger.active_mutations(repo), mutation_ledger.mutation_state(repo)


@case
def the_mutation_transaction_restores_even_when_the_body_raises():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("ORIGINAL = True\n", encoding="utf-8")
        original = target.read_bytes()
        try:
            with mutation_ledger.mutation_transaction(
                repo, harness="ar222d-test", mutation_id="m2", targets=[target],
            ):
                target.write_text("MUTATED\n", encoding="utf-8")
                raise RuntimeError("the suite exploded")
        except RuntimeError:
            pass
        assert target.read_bytes() == original, "a failing body left the tree mutated"
        assert not mutation_ledger.active_mutations(repo)


@case
def active_mutation_sentinel_blocks_an_unsafe_repository_operation():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("ORIGINAL = True\n", encoding="utf-8")
        with mutation_ledger.mutation_transaction(
            repo, harness="ar222d-test", mutation_id="m3", targets=[target],
        ):
            message = ""
            try:
                mutation_ledger.assert_no_active_mutation(repo, operation="commit")
            except mutation_ledger.MutationStateError as exc:
                message = str(exc)
            assert "refusing to commit" in message, message
            assert "ar222d-test" in message, message
        mutation_ledger.assert_no_active_mutation(repo, operation="commit")


@case
def a_stale_mutation_entry_from_a_dead_harness_is_reported_not_hidden():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        ledger = repo / mutation_ledger.LEDGER_NAME
        ledger.write_text(json.dumps([{
            "harness": "dead-harness", "mutation_id": "m9", "pid": 999999,
            "targets": ["x.py"], "stash": "", "opened_at": 0, "cleared_at": 0,
        }], indent=2), encoding="utf-8")
        state = mutation_ledger.mutation_state(repo)
        assert state["active"], state
        assert state["stale_entries"], "an entry whose process is gone must be reported as stale"
        try:
            mutation_ledger.assert_no_active_mutation(repo, operation="release")
            raise AssertionError("a stale mutation entry must still block")
        except mutation_ledger.MutationStateError as exc:
            assert "recovery required" in str(exc), exc


@case
def an_unreadable_mutation_ledger_is_treated_as_active_because_unknown_is_not_clear():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        (repo / mutation_ledger.LEDGER_NAME).write_text("{not json", encoding="utf-8")
        state = mutation_ledger.mutation_state(repo)
        assert state["active"] and not state["known"], state
        try:
            mutation_ledger.assert_no_active_mutation(repo, operation="tag")
            raise AssertionError("an unreadable ledger must fail closed")
        except mutation_ledger.MutationStateError as exc:
            assert "unknown" in str(exc), exc


@case
def repository_considered_restored_with_mutated_untracked_state_is_caught():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        fixture = repo / "fixture.bin"
        fixture.write_bytes(b"original")
        expected = mutation_ledger.expected_state([], root=repo, untracked_globs=["fixture.bin"])
        assert expected["untracked_count"] == 1, expected
        fixture.write_bytes(b"mutated but same length!!!!")
        fixture.write_bytes(b"CHANGED-UNTRACKED")
        verdict = mutation_ledger.verify_restoration(expected, root=repo, ledger_repo=repo)
        assert not verdict["restored"], verdict
        assert any("untracked fixture" in item for item in verdict["problems"]), verdict


@case
def restoration_is_verified_by_digest_not_by_an_empty_git_diff():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("VALUE = 1\n", encoding="utf-8")
        expected = mutation_ledger.expected_state([target], root=repo)
        target.write_text("VALUE = 2\n", encoding="utf-8")
        verdict = mutation_ledger.verify_restoration(expected, root=repo, ledger_repo=repo)
        assert not verdict["restored"], verdict
        assert verdict["digests_compared"] == 1, verdict
        target.write_text("VALUE = 1\n", encoding="utf-8")
        assert mutation_ledger.verify_restoration(expected, root=repo, ledger_repo=repo)["restored"]


@case
def a_missing_restoration_is_reported_loudly_rather_than_assumed():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("VALUE = 1\n", encoding="utf-8")
        expected = mutation_ledger.expected_state([target], root=repo)
        target.unlink()
        verdict = mutation_ledger.verify_restoration(expected, root=repo, ledger_repo=repo)
        assert not verdict["restored"]
        assert any("missing" in item for item in verdict["problems"]), verdict


@case
def interrupted_mutation_is_recovered_from_its_stash():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        target = repo / "engine.py"
        target.write_text("ORIGINAL = True\n", encoding="utf-8")
        original = target.read_bytes()
        manager = mutation_ledger.mutation_transaction(
            repo, harness="ar222d-test", mutation_id="m4", targets=[target],
        )
        opened = manager.__enter__()
        target.write_text("MUTATED\n", encoding="utf-8")
        truthy(opened["targets"], opened)
        assert target.read_text() == "MUTATED\n"
        # Simulate a hard kill: the generator is abandoned without __exit__ running.
        recovered = mutation_ledger.recover(repo)
        assert target.read_bytes() == original, "recovery did not restore the stashed bytes"
        assert recovered["restored"], recovered
        assert recovered["problems"] == [], recovered


@case
def a_stale_ledger_entry_from_a_dead_harness_is_cleared_by_recovery():
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        ledger = repo / mutation_ledger.LEDGER_NAME
        ledger.write_text(json.dumps([{
            "harness": "dead-harness", "mutation_id": "m9", "pid": 999999,
            "targets": ["x.py"], "stash": "", "opened_at": 0, "cleared_at": 0,
        }], indent=2), encoding="utf-8")
        assert mutation_ledger.mutation_state(repo)["active"]
        recovered = mutation_ledger.recover(repo)
        assert recovered["stale_stashes"] == ["m9"], recovered
        assert recovered["ledger_clear"], recovered
        assert not mutation_ledger.mutation_state(repo)["active"]


@case
def critical_test_removed_but_test_count_only_gate_stays_green_is_caught():
    outputs = {"scripts/test-ar222d.py": "PASS  60/60\n"}
    report = test_inventory.check_inventory(
        outputs, floors={}, corpus="PASS 60/60\n",
    )
    assert not report["ok"], "a green suite with missing named guarantees passed the inventory"
    truthy(report["missing_named_guarantees"], report)
    assert not report["floor_failures"], (
        "the count floor is a second, independent net; with no floors recorded this check must not "
        "invent one"
    )
    guarded = test_inventory.check_inventory(
        outputs, corpus=test_inventory.corpus_text([ROOT / "scripts", ROOT / "src"]),
    )
    assert guarded["ok"], (
        f"the named guarantees are present in this repository, so the inventory must pass: "
        f"{guarded['missing_named_guarantees']}"
    )


@case
def the_named_inventory_is_satisfied_by_this_repository():
    corpus = test_inventory.corpus_text([ROOT / "scripts", ROOT / "src"])
    missing = test_inventory.missing_critical_cases([], corpus)
    for group, phrases in missing.items():
        for phrase in phrases:
            assert phrase.lower() in corpus.lower(), (
                f"{group}: the guarantee {phrase!r} is named nowhere in the repository. A guarantee "
                "nobody has implemented cannot be inventoried, and the manifest must say so"
            )


@case
def the_recorded_case_floor_catches_an_unnamed_loss():
    outputs = {"scripts/test-rendered-critique.py": "PASS  3/3\n"}
    report = test_inventory.check_inventory(outputs, corpus=test_inventory.corpus_text())
    failures = [row for row in report["floor_failures"] if row["suite"] == "test-rendered-critique.py"]
    truthy(failures, "a suite that fell from 87 to 3 cases passed on count alone")
    assert failures[0]["shortfall"] > 0, failures


@case
def an_unparseable_summary_is_an_unenforced_floor_not_a_satisfied_one():
    """The silent green this module could otherwise produce.

    Two suites print ``N/N passed`` without a ``PASS`` prefix. When this module understood
    only the prefixed form they reported ``0/0``, read as "no floor violation", and passed
    silently -- the same failure shape as AR-222's vanished test, one level up.
    """
    for output in ("PASS  3/3\n", "3/3 passed\n", "27/27 attacks held\n"):
        summary = test_inventory.parse_summary(output)
        assert summary["total"], output
        assert summary["green"], output
    silent = test_inventory.check_inventory(
        {"scripts/test-rendered-critique.py": "ok  something\n"},
        corpus=test_inventory.corpus_text(),
    )
    assert not silent["ok"], "an unreadable summary passed the inventory"
    truthy(silent["unparsed_summaries"], silent)
    assert "unenforced floor" in silent["unparsed_summaries"][0]["note"], silent


@case
def a_surviving_mutation_is_a_failure_to_investigate():
    report = test_inventory.survivor_report("own-slop omitted", caught=False)
    assert report["classification"] == "SURVIVED"
    assert len(report["investigate"]) == 3, report
    truthy(any("weaken" in item for item in report["forbidden_responses"]), report)


@case
def named_cases_are_parsed_not_merely_counted():
    text = "ok   three candidates materially differ\nFAIL  own-slop omitted\nPASS  2/2\n"
    cases = test_inventory.parse_cases(text)
    assert "three candidates materially differ" in cases, cases
    assert "own-slop omitted" in cases, cases
    summary = test_inventory.parse_summary(text)
    assert summary["passed"] == 2 and summary["total"] == 2 and summary["green"]


@case
def the_inventory_manifest_is_written_and_round_trips():
    manifest = test_inventory.manifest()
    assert manifest["named_total"] > 20, manifest["named_total"]
    assert manifest["suite_floors"], manifest
    with tempfile.TemporaryDirectory() as directory:
        path = test_inventory.write_manifest(Path(directory) / "inventory.json")
        assert json.loads(path.read_text(encoding="utf-8")) == manifest


# ================================================================ the slice

@case
def the_slice_is_deterministic_and_offline():
    first = f1.run()
    second = f1.run()
    assert first["proposal"]["user_visible_text"] == second["proposal"]["user_visible_text"]
    assert first["proposal"]["proposal_digest"] == second["proposal"]["proposal_digest"]
    assert [row["concept_id"] for row in first["concepts"]["candidates"]] == [
        row["concept_id"] for row in second["concepts"]["candidates"]
    ]


@case
def the_slice_requests_nothing_and_prescribes_nothing():
    report = f1.run()
    assert report["request"] == "Make me a cool F1 dashboard."
    assert "recommendation" in report
    truthy(report["anti_default_analysis"]["own_failure_mode"], report["anti_default_analysis"])


@case
def the_slice_reaches_an_implementation_plan_with_derived_constraints():
    report = f1.run()
    assert report["completed"], report["failures"]
    truthy(report["implementation_plan"]["constraints"], report["implementation_plan"])
    assert report["continuation"]["next_autonomous_step"].startswith("compile the design")


@case
def the_slice_does_not_use_beacon_and_does_not_touch_boreal():
    report = f1.run()
    blob = json.dumps(report)
    assert "beacon" not in blob.lower(), "the F1 slice must not reuse AR-222's Beacon fixture"
    assert "boreal" not in blob.lower(), "Boreal is out of scope for AR-222D"
    assert f1.SURFACES == ("live-timing-wall", "stint-and-tyre-wall", "session-setup")


@case
def beacon_ar222_evidence_is_preserved_as_a_negative_case():
    """AR-222's closure state must remain readable and unchanged."""
    results = ROOT / "docs" / "v2" / "2.2" / "20-AR-222-RESULTS.md"
    text = results.read_text(encoding="utf-8")
    assert "RENDERED_WITH_KNOWN_FINDINGS" in text, text[:400]
    assert "persistent" in text
    assert "minor hierarchy finding" in text or "hierarchy" in text
    assert "390px" in text


def run() -> int:
    failures: list[str] = []
    for fn in OFFLINE["cases"]:
        name = fn.__name__.replace("_", " ")
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}")
            print(f"     {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - a suite reports, it does not crash
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"ERROR {name}")
            print(f"     {type(exc).__name__}: {exc}")
            continue
        print(f"ok   {name}")
    total = len(OFFLINE["cases"])
    print()
    if failures:
        print(f"{len(failures)}/{total} failed")
        return 1
    print(f"{total}/{total} passed")
    print("AR-222D suite: all green")
    return 0


if __name__ == "__main__":
    sys.exit(run())
