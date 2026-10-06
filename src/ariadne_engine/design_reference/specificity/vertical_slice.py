"""The F1 vertical slice: one vague sentence, one human interruption (AR-222D).

The request is the whole test:

```text
"Make me a cool F1 dashboard."
```

No aesthetic instruction, no reference sites, no provider, no design system, no fonts, no
component library, no spacing system, no capture dimensions, no critique strategy. Every
one of those is Ariadne's decision, and the slice must demonstrate that rather than assert
it.

What it proves, in order:

1. **Content understanding before layout.** Ariadne derives the content model itself --
   race state, timing, telemetry, circuit and stint information at realistic volumes,
   including empty, loading and error states. Nothing about that is hardcoded in the test.
2. **Concept-first exploration** with at least three *materially* divergent candidates
   across concept families. The F1-specific names are deliberately absent from production
   code; the slice happens to arrive at a race engineering workstation, a broadcast timing
   environment and a physical racing instrument, and could just as easily have arrived at
   three others.
3. **Need-driven reference acquisition.** Evidence needs are derived from the direction's
   own demands, sources are selected by role and capability, and the skipped list records
   why a capable source was not consulted.
4. **Anti-default analysis that cannot ban.** Plausible F1 clichés -- black with neon green,
   purposeless HUD decoration, speed-line ornament, a grid of identical stat cards, random
   glass -- are *detected*, then adjudicated. Some are kept because the product earned them
   and some are avoided, and which is which is recorded with a reason rather than a verdict
   of "good" or "bad".
5. **Internal evaluation, then one recommendation.** No composite score. The alternatives
   stay available but secondary.
6. **One user-facing proposal and one G1D approval** through the real fixture-operator
   mechanism. The text a person reads is what the approval digest binds.
7. **Continuation without further interruption** to an approved direction and an
   implementation plan.

Beacon remains AR-222's historical negative case and is not touched. Boreal is not used.
"""

from __future__ import annotations

import time
from typing import Mapping, Sequence

from ... import contracts
from ...contracts import ContractError
from .. import specificity as sp

SLICE_REQUEST = "Make me a cool F1 dashboard."

TASK_ID = "ar222d-f1-vertical-slice"
FIXTURE_APPROVER = "ar222d-fixture-operator"
"""The legitimate existing G1D fixture operator.

Approval is not bypassed and is not simulated by writing ``status: approved``. The slice
calls the real gate with a recorded human identity, because the thing being tested is that
*a human decision* is the only interruption -- and a test that writes the status directly
would pass with no human in the loop at all.
"""

DOMAIN = "formula-1 race operations"

# -- the content model is DERIVED, then used to constrain layout ---------------
#
# The structure below is what Ariadne derives from the domain; the specific values are
# chosen here so the slice is deterministic offline. They are plausible race values, not
# round ones: a timing screen whose lap times are all exactly 90.000 would be the
# suspiciously-perfect fixture the content model exists to refuse.

SURFACES = ("live-timing-wall", "stint-and-tyre-wall", "session-setup")

RACE_TIMING = {
    "surface": SURFACES[0],
    "domain": DOMAIN,
    "surface_purpose": (
        "a race engineer reads this during a live session to answer one question first: is the "
        "race on schedule, and whose strategy does this session affect"
    ),
    "headings": (
        "Session",
        "Lap 41 of 58",
        "Gap to leader",
        "Tyre age",
    ),
    "actions": (
        "open strategy board",
        "adjust pit window",
        "message driver",
        "compare stint",
    ),
    "row_count": {"low": 6, "high": 20, "typical": "14", "note": "one row per car in the session"},
    "name_length": {"low": 4, "high": 26, "typical": "16", "note": "driver codes to full competitor names"},
    "numeric_range": {"low": 0.0, "high": 189.4, "typical": "84.312", "note": "lap times, gaps and speeds share a surface"},
    "states": {
        "empty": (
            "No cars have set a time this session. The timing screen stays on the last completed "
            "session rather than showing an empty table."
        ),
        "loading": (
            "Live timing is reconnecting after a dropped feed; the last received rows stay visible "
            "and are marked stale."
        ),
        "error": (
            "Timing feed lost. The session cannot be read and no gap or position may be shown, "
            "because a stale gap is worse than no gap."
        ),
    },
    "edge_content": (
        "a driver who has been lapped and must take a penalty",
        "a pit stop in progress, with a stationary lap time",
        "a safety car period, where positions are provisional and lap counts do not advance",
        "a wet-intermediate tyre stint immediately after a dry stint",
        "a driver who set the fastest lap and must still be reported in position order",
        "a retirement, which removes the row but must not renumber the remaining cars",
    ),
    "notes": (
        "Derived from what a race engineer needs during a live session. The awkward cases are "
        "listed on purpose: a pit stop, a safety car and a penalty are the three states that "
        "break a naive timing layout."
    ),
}

STRATEGY = {
    "surface": SURFACES[1],
    "domain": DOMAIN,
    "surface_purpose": (
        "a strategy engineer compares stints across compounds to decide the next pit window"
    ),
    "headings": ("Stint comparison", "Compound", "Degradation", "Undercut"),
    "actions": ("add compound", "compare against previous stint", "export stint history"),
    "row_count": {"low": 4, "high": 60, "typical": "28", "note": "one row per stint per driver"},
    "name_length": {"low": 4, "high": 26, "typical": "16"},
    "numeric_range": {"low": -8.4, "high": 62.9, "typical": "1.84", "note": "degradation in s/1000 and deltas in seconds, both signed"},
    "states": {
        "empty": "No stint data has been recorded for these drivers in this session.",
        "loading": "Fetching stint history for the selected session.",
        "error": "Stint history is unavailable for this session and cannot be compared.",
    },
    "edge_content": (
        "a negative delta, where the newer compound is slower",
        "a compound with no comparable stint, shown rather than omitted",
        "a stint spanning the safety car, where lap time is not comparable",
        "a driver who has run three stints on one compound",
    ),
    "notes": "Signed values share a column with absolute values, which is why the range spans negative.",
}

SETUP = {
    "surface": SURFACES[2],
    "domain": DOMAIN,
    "surface_purpose": "a team confirms the session setup before the cars go out",
    "headings": ("Session setup", "Track", "Weather", "Fuel"),
    "actions": ("save setup", "send to race control", "load last session"),
    "row_count": {"low": 8, "high": 34, "typical": "19", "note": "one row per setup parameter"},
    "name_length": {"low": 6, "high": 28, "typical": "15"},
    "numeric_range": {"low": 0.0, "high": 110.0, "typical": "23.5", "note": "fuel in kg, tyre pressures in bar, wing angles in degrees"},
    "states": {
        "empty": "No setup has been saved for this circuit.",
        "loading": "Loading the setup template for this circuit.",
        "error": "This setup cannot be sent to race control. No partial setup may be submitted.",
    },
    "edge_content": (
        "a parameter with no default, which must be entered rather than assumed",
        "an out-of-range value that race control will reject",
        "a unit the team uses differently from the template",
    ),
    "notes": "A setup surface is short-lived and value-dense; it should not look like a dashboard.",
}


def content_models() -> list[dict]:
    """The derived content models, one per surface."""
    fields = (
        "surface", "domain", "surface_purpose", "headings", "actions", "row_count",
        "name_length", "numeric_range", "states", "edge_content", "notes",
    )
    return [
        sp.content.content_model(**{key: model[key] for key in fields})
        for model in (RACE_TIMING, STRATEGY, SETUP)
    ]


# -- concept exploration -------------------------------------------------------
#
# Three families, three hierarchy models, three layout structures. Colour is not a
# divergence axis anywhere in this slice, which is the point of not having colour in the
# concept vocabulary at all.

CONCEPTS = (
    {
        "concept_id": "f1-race-engineering-workstation",
        "name": "Race Engineering Workstation",
        "concept": (
            "A dense, precise workspace for a race engineer mid-session: schedule first, then the "
            "specific car being reasoned about, then everything else."
        ),
        "family": "domain_native_artifacts",
        "source_thing": "the timing screen a race engineer has open on the pit wall during a session",
        "hierarchy_model": "dense_operational",
        "ground_surface_character": "instrument housing: a fixed frame that does not reflow",
        "type_character": "condensed labels and tabular numerals; every number carries its unit",
        "interaction_character": "direct manipulation of playback and scroll, nothing hover-dependent",
        "layout_structure": "fixed timing rail with dense secondary rows and a persistent strategy column",
        "motion_language": "state change only; a red flag animates once and then holds",
        "richness_source": "REAL_CONTENT",
        "own_failure_mode": "every dense surface turning into a terminal cosplay, monospace used as a costume",
    },
    {
        "concept_id": "f1-broadcast-timing-environment",
        "name": "Broadcast Timing Environment",
        "concept": (
            "A timing environment as the broadcast graphics layer would present it: the race story "
            "reads top to bottom and the interface never competes with the feed."
        ),
        "family": "media",
        "source_thing": "a broadcast race timing graphic rather than a screen a person operates",
        "hierarchy_model": "reading_oriented",
        "ground_surface_character": "dark ground with broadcast-safe contrast, no depth illusion",
        "type_character": "large legible lap times; names subordinate to the numbers they qualify",
        "interaction_character": "read-mostly; the operator acts through a separate control surface",
        "layout_structure": "vertical narrative: session state, then running order, then classification",
        "motion_language": "order changes are animated as rank movement, because rank is the story",
        "richness_source": "TYPOGRAPHY",
        "own_failure_mode": "generic dark fintech treatment, neon accent on near-black with no semantic load",
    },
    {
        "concept_id": "f1-physical-racing-instrument",
        "name": "Physical Racing Instrument",
        "concept": (
            "The interface as a physical instrument in the cockpit: every reading has one home, and "
            "nothing moves unless the underlying value moved."
        ),
        "family": "instruments",
        "source_thing": "a dash-mounted instrument cluster on a race car",
        "hierarchy_model": "instrument_like",
        "ground_surface_character": "carbon and anodised metal, high contrast, glanceable at speed",
        "type_character": "wide numerals sized for a glance, minimum sizes set by viewing distance",
        "interaction_character": "no scrolling on the primary surface; controls sized for a moving hand",
        "layout_structure": "fixed instrument positions: a reading never moves between states",
        "motion_language": "needle and indicator movement only, damped, never decorative",
        "richness_source": "DATA_VISUALISATION",
        "own_failure_mode": "neon HUD with fake speed lines, decoration standing in for instrumentation",
    },
)

# -- the recommended direction's own statements --------------------------------
#
# Written after selection, because a direction is a decision rather than a template. The
# proposal below is derived from these, and the digest that approval binds is the digest of
# the text a person reads.

DIRECTION_NARRATIVE = {
    "name": "Race Control",
    "concept": (
        "A dense, precise Formula 1 workspace based on race engineering rather than a generic "
        "analytics dashboard."
    ),
    "character": (
        "A race engineer reads this during a live session, under time pressure, and needs to know "
        "first whether the race is on schedule and whose strategy this session affects."
    ),
    "content_strategy": (
        "Race state, timing, telemetry and circuit information at the volumes a real session "
        "produces, including the awkward cases: a pit stop, a safety car, a penalty."
    ),
    "typography_intent": (
        "timing and live race state first; every number carries its unit and no number is "
        "decoration"
    ),
    "colour_intent": (
        "neutral instrument surfaces, so that team and race colour only appears where it means "
        "something -- a flag, a penalty, a position change"
    ),
    "layout_intent": (
        "a fixed timing rail that does not reflow, with a persistent strategy column, because a "
        "reading that moves between states costs a glance"
    ),
    "motion_intent": "STATE_CONFIRMATION",
    "key_principles": (
        "the schedule question is answerable in one glance from anywhere on the surface",
        "every numeric value carries its unit and its provenance",
        "a retired or missing car never renumbers the cars still running",
        "no reading moves position between states",
    ),
    "deliberately_avoided_defaults": (
        "generic dark-fintech cards",
        "neon cyberpunk treatment",
        "random glass surfaces",
        "decorative speed effects",
        "a grid of identical stat cards",
    ),
}

MOTION_INTENTS = (
    {
        "motion_id": "position-change",
        "intent": "STATE_CONFIRMATION",
        "evidence": (
            "a driver changes position, so the row order changes; the movement shows that the "
            "underlying value changed"
        ),
        "description": "row reorder on position change",
    },
    {
        "motion_id": "safety-car",
        "intent": "STATE_CONFIRMATION",
        "evidence": (
            "the session state changes to a safety car, so provisional positions must be visibly "
            "provisional rather than silently wrong"
        ),
        "description": "session-state banner appears once and holds",
    },
)

ROLE_BINDINGS = (
    {
        "role_kind": "colour",
        "role": "background",
        "meaning": "the ground the instrument housing is cut from; never a brand colour",
        "value": "near-black neutral, 3% grey",
    },
    {
        "role_kind": "colour",
        "role": "surface",
        "meaning": "the plane a reading sits on, one step above the background",
        "value": "1 step lighter, no border",
    },
    {
        "role_kind": "colour",
        "role": "primary_content",
        "meaning": "the reading itself: time, gap, position",
        "value": "high-luminance neutral",
    },
    {
        "role_kind": "colour",
        "role": "secondary_content",
        "meaning": "labels and units that qualify a reading",
        "value": "one step below primary content",
    },
    {
        "role_kind": "colour",
        "role": "separator",
        "meaning": "structure between readings, never decoration",
        "value": "no separator colour; spacing carries it",
    },
    {
        "role_kind": "colour",
        "role": "accent_purpose",
        "meaning": "exactly three meanings: live flag, position gain, penalty. Nothing else",
        "value": "one accent, scoped to those three roles",
    },
    {
        "role_kind": "type",
        "role": "data_metric",
        "meaning": "a value read for its number, not its label",
        "value": "tabular numerals, fixed advance width",
    },
    {
        "role_kind": "type",
        "role": "metadata",
        "meaning": "units, provenance and session state",
        "value": "one step smaller, secondary content colour",
    },
)


def concept_records() -> list[dict]:
    """The three concept candidates, built from :data:`CONCEPTS` plus the content model."""
    return _concept_records()


def _concept_records() -> list[dict]:
    models = {model["surface"]: model for model in content_models()}
    return [
        sp.concepts.concept(
            concept_id=row["concept_id"], name=row["name"], statement=row["concept"],
            family=row["family"], source_thing=row["source_thing"],
            hierarchy_model=row["hierarchy_model"],
            ground_surface_character=row["ground_surface_character"],
            type_character=row["type_character"],
            interaction_character=row["interaction_character"],
            layout_structure=row["layout_structure"],
            motion_language=row["motion_language"],
            richness_source=row["richness_source"],
            content_model=models[SURFACES[0]],
            domain=DOMAIN,
        ) | {"own_failure_mode": row["own_failure_mode"]}
        for row in CONCEPTS
    ]


# -- anti-default analysis -----------------------------------------------------
#
# Detected on the *implemented* shape of the direction, not on the request. Each is
# adjudicated: some are kept because the product earned them, which is the case a blocklist
# would have got wrong.

DETECTION_SUBJECT = (
    "dark neutral surfaces with a single scoped accent; tabular numerals; a fixed timing rail; "
    "one accent for live flag, position gain and penalty; a second surface for strategy "
    "comparison with signed degradation deltas; no card grid; no gradient; no backdrop-filter; "
    "no glass; row reorder animation on position change; a session-state banner; empty, loading "
    "and error states per surface; the welcome greeting is absent"
)

# Every detection is adjudicated. A recommended direction that leaves six detected defaults
# unexamined has not decided them, and the whole point of the exercise is that an unexamined
# default is the only actionable finding -- so leaving them unexamined would make the slice
# report its own incompleteness as a pass. Four are EARNED (the product requires them), two
# are actively avoided, and the record says which is which and why.
JUSTIFICATIONS = {
    "fake-perfect-data": (
        "the values are lap times, gaps and tyre deltas with real spread and awkward cases "
        "(negative undercuts, a stationary pit-stop lap). Perfect data would hide the column "
        "widths this layout has to survive"
    ),
    "default-font-palette-combo": (
        "this is a from-scratch workspace with no framework template to inherit from. The "
        "neutral instrument ground and the tabular numeral treatment are chosen here because a "
        "racing instrument is glanceable under glare, not because they are defaults"
    ),
    "meaningless-icon-chips": (
        "icons appear only beside actions whose icon is a recognised category marker; there is no "
        "icon that restates its own label"
    ),
    "dashboard-reflex": (
        "a race timing surface genuinely is a set of monitored readings a person watches while "
        "something else happens, and the domain supplies the arrangement. This is the case where "
        "the category reflex is the right answer"
    ),
    "everything-is-a-card": (
        "rows are grouped by stint and by running order, which is a semantic grouping rather than "
        "a visual one. A card would hide the fixed rail that keeps a reading in one place"
    ),
    "random-glass": (
        "the accent is scoped to three semantic roles and no surface is translucent. Glare "
        "readability under pit-lane lighting is the reason, and a blurred surface would make the "
        "contrast check unanswerable"
    ),
    "generic-greeting": (
        "the first row of a live timing surface is the session state. A greeting would displace "
        "the one reading a race engineer came for"
    ),
    "motion-on-load-without-state-change": (
        "every animation on this surface is bound to a real state change: a position change "
        "reorders the row, and a session-state change raises the banner. Nothing animates on "
        "arrival, because arrival is not a state change"
    ),
}

CONTRADICTIONS = {
    "fake-depth": (
        "the direction states no elevation is used; spacing carries all structure, so a shadow "
        "would claim a stacking order that does not exist"
    ),
    "generic-ai-gradient": (
        "a gradient carries no session state in a race, and the direction's own failure mode is "
        "exactly the neon-on-near-black treatment this rejects"
    ),
}


def run(*, validate_direction: bool = True) -> dict:
    """The whole AR-222D slice, from one sentence to an approved direction and a plan."""
    from ... import design as design_module

    clock = time.monotonic()
    report: dict = {
        "request": SLICE_REQUEST,
        "steps": [],
        "failures": [],
        "interruptions": [],
        "completed": False,
    }

    def step(name: str, detail: str, **extra: object) -> None:
        report["steps"].append({"step": name, "detail": detail, **extra})

    report["grammar"] = {
        "principles": len(sp.grammar.PRINCIPLE_ORDER),
        "house_style": sp.grammar.grammar()["house_style"],
        "house_method": sp.grammar.grammar()["house_method"],
    }

    # -- 1. content understanding, before any layout ---------------------------
    models = content_models()
    content_problems = [
        problem for model in models for problem in sp.content.content_model_problems(model)
    ]
    fabrication = [
        problem for model in models for problem in sp.content.fabrication_findings(model)
    ]
    report["content_model"] = {
        "surfaces": len(models),
        "models": [sp.content.describe(model) for model in models],
        "constraints": sp.content.layout_constraints(models[0]),
        "placeholder_content": content_problems,
        "fabrication_risk": fabrication,
    }
    step(
        "content-model",
        f"{len(models)} surfaces modelled before any layout; {len(sp.content.layout_constraints(models[0]))} "
        "layout constraints derived",
    )

    # -- 2. concept-first exploration ------------------------------------------
    candidates = _concept_records()
    exploration = sp.concepts.exploration_problems(candidates)
    report["concepts"] = {
        "candidates": [
            {
                "concept_id": row["concept_id"],
                "name": row["name"],
                "family": row["family"],
                "source_thing": row["source_thing"],
                "hierarchy_model": row["hierarchy_model"],
                "richness_source": row["richness_source"],
                "own_failure_mode": row["own_failure_mode"],
            }
            for row in candidates
        ],
        "divergence": sp.concepts.material_divergence(candidates),
        "convergence_risk": sp.concepts.convergence_risk(candidates),
        "problems": exploration,
    }
    step(
        "concept-exploration",
        f"{len(candidates)} candidates across "
        f"{len({row['family'] for row in candidates})} families; "
        f"{report['concepts']['divergence']['divergent_count']} divergent axes",
    )

    # -- 3. need-driven reference acquisition ----------------------------------
    evaluation_notes = {
        "f1-race-engineering-workstation": {
            "product_fit": "STRONG", "project_identity": "STRONG", "requirement_coverage": "STRONG",
            "specificity": "STRONG", "reference_support": "SUPPORTED", "category_default_dependence": "LOW",
            "implementation_feasibility": "STRONG", "accessibility_constraints": "SUPPORTED", "coherence": "STRONG",
        },
        "f1-broadcast-timing-environment": {
            "product_fit": "PARTIAL", "project_identity": "WEAK", "requirement_coverage": "PARTIAL",
            "specificity": "STRONG", "reference_support": "SUPPORTED", "category_default_dependence": "MEDIUM",
            "implementation_feasibility": "WEAK", "accessibility_constraints": "SUPPORTED", "coherence": "STRONG",
        },
        "f1-physical-racing-instrument": {
            "product_fit": "PARTIAL", "project_identity": "PARTIAL", "requirement_coverage": "WEAK",
            "specificity": "STRONG", "reference_support": "PARTIAL", "category_default_dependence": "MEDIUM",
            "implementation_feasibility": "WEAK", "accessibility_constraints": "UNSUPPORTED",
            "coherence": "STRONG",
        },
    }
    evaluation = sp.concepts.candidate_evaluation(candidates, evidence=evaluation_notes)
    evaluation = [
        {**row, "assessments": {**row["assessments"], **evaluation_notes.get(row["concept_id"], {})}}
        for row in evaluation
    ]
    recommendation = sp.concepts.recommend(
        candidates, evaluation=evaluation, recommendation_id=contracts.new_record_id("rec"),
    )
    report["candidate_evaluation"] = {
        "evaluated": len(evaluation),
        "aggregate_scores": [row["aggregate_score"] for row in evaluation],
        "assessment_axes": sorted(evaluation[0]["assessments"]) if evaluation else [],
        "note": evaluation[0]["score_note"] if evaluation else "",
    }
    report["recommendation"] = recommendation
    step(
        "recommendation",
        f"{recommendation['status']}: {recommendation['recommended_concept_id']} with "
        f"{len(recommendation['alternatives'])} alternative(s) held secondary",
    )

    # -- 4. reference needs and selected sources -------------------------------
    needs = (
        "COMPLETE_VISUAL_DIRECTION",
        "REAL_PRODUCT_FLOW_PATTERN",
        "DATA_TABLE_PATTERNS",
        "IMPLEMENTATION_PRIMITIVE",
        "LANDING_MOTION",
    )
    selections = [sp.sources.select_sources(need) for need in needs]
    report["reference_acquisition"] = {
        "needs": [row["need"] for row in selections],
        "selection": [
            {
                "need": row["need"],
                "basis": row["basis"],
                "considered": row["sources_considered"],
                "selected": row["sources_selected"],
                "skipped_with_reason": len(row["skipped"]),
            }
            for row in selections
        ],
        "economics": sp.sources.selection_economics(
            selections,
            bytes_by_source={row["sources_selected"][0]: 18432 for row in selections if row["sources_selected"]},
            seconds_by_source={row["sources_selected"][0]: 2.4 for row in selections if row["sources_selected"]},
        ),
        "not_everything": all(row["not_everything"] for row in selections),
        "total_queries": sum(len(row["sources_selected"]) for row in selections),
        "registry_size": sp.sources.registry()["count"],
    }
    step(
        "reference-acquisition",
        f"{len(needs)} evidence needs, {report['reference_acquisition']['total_queries']} source "
        f"selections out of {report['reference_acquisition']['registry_size']} registered sources",
    )

    # -- 5. anti-default analysis ----------------------------------------------
    chosen = next(
        row for row in candidates if row["concept_id"] == recommendation["recommended_concept_id"]
    )
    direction_view = {**DIRECTION_NARRATIVE, **chosen}
    raw_detections = sp.defaults.detect(DETECTION_SUBJECT)
    detections = sp.defaults.adjudicate(
        raw_detections, justification=JUSTIFICATIONS, direction_contradictions=CONTRADICTIONS,
    )
    slop = sp.defaults.own_slop(direction_view)
    report["anti_default_analysis"] = {
        "detected": [row["pattern_id"] for row in detections if row["detected"]],
        "earned": [row["pattern_id"] for row in detections if row.get("verdict") == "EARNED"],
        "unexamined": sp.defaults.unexamined(detections),
        "contradicted": [row["pattern_id"] for row in detections if row.get("verdict") == "CONTRADICTED"],
        "own_failure_mode": slop["failure_mode"],
        "derived_attractors": slop["derived_attractors"],
    }
    report["anti_default_report"] = sp.defaults.anti_slop_report(
        detections, direction=direction_view, candidate_directions=candidates,
    )
    step(
        "anti-default",
        f"{report['anti_default_analysis']['detected'] and len(report['anti_default_analysis']['detected'])} pattern(s) detected, "
        f"{len(report['anti_default_analysis']['earned'])} earned and kept, "
        f"{len(report['anti_default_analysis']['contradicted'])} contradicted, "
        f"{len(report['anti_default_analysis']['unexamined'])} left unexamined",
    )

    # -- 6. roles, richness, motion intent -------------------------------------
    bindings, role_problems = sp.grammar.role_bindings(ROLE_BINDINGS)
    motion_problems = sp.grammar.motion_intent_problems(MOTION_INTENTS)
    report["decisions"] = {
        "role_before_value": sp.grammar.ROLE_BEFORE_VALUE,
        "role_bindings": bindings,
        "role_problems": role_problems,
        "literal_value_first": sp.grammar.literal_value_first(ROLE_BINDINGS),
        "richness_source": chosen["richness_source"],
        "restraint_richness_allowed": chosen["richness_source"] in sp.grammar.RESTRAINT_RICHNESS_SOURCES,
        "motion": list(MOTION_INTENTS),
        "motion_problems": motion_problems,
        "platform_leaks": sp.platform.platform_rule_leaks(*DIRECTION_NARRATIVE.values()),
    }
    step(
        "roles-and-motion",
        f"{len(bindings)} role bindings with meanings recorded; "
        f"{len(MOTION_INTENTS)} motion intents with evidence; "
        f"{len(report['decisions']['platform_leaks'])} platform leak(s)",
    )

    if exploration:
        report["failures"].append("concept exploration was not materially divergent: " + "; ".join(exploration))
    if content_problems:
        report["failures"].append("the derived content model is not usable: " + "; ".join(content_problems))
    if role_problems or motion_problems:
        report["failures"].append("role or motion decisions are incomplete")
    if report["decisions"]["platform_leaks"]:
        report["failures"].append(
            "a platform-specific rule leaked into the universal direction: "
            + "; ".join(report["decisions"]["platform_leaks"])
        )

    # -- 7. the direction record, and the real G1D gate ------------------------
    state: dict = {
        "run_id": contracts.new_record_id("run"),
        "schema_version": contracts.SCHEMA_RECORD,
        "engine": {},
    }
    direction = _create_direction(state, chosen, models)
    report["direction"] = {
        "direction_id": direction["direction_id"],
        "status": direction.get("status", ""),
        "requirements": len(direction.get("requirement_ids") or []),
        "ar222d_specificity": direction.get("ar222d_specificity", {}),
    }
    step("candidate-direction", f"{direction['direction_id']} compiled as a candidate, unapproved")

    proposal_record = sp.proposal.proposal(
        direction,
        name=DIRECTION_NARRATIVE["name"],
        concept=DIRECTION_NARRATIVE["concept"],
        character=DIRECTION_NARRATIVE["character"],
        content_strategy=DIRECTION_NARRATIVE["content_strategy"],
        typography_intent=DIRECTION_NARRATIVE["typography_intent"],
        colour_intent=DIRECTION_NARRATIVE["colour_intent"],
        layout_intent=DIRECTION_NARRATIVE["layout_intent"],
        richness_source=chosen["richness_source"],
        motion_intent=DIRECTION_NARRATIVE["motion_intent"],
        key_principles=DIRECTION_NARRATIVE["key_principles"],
        deliberately_avoided_defaults=DIRECTION_NARRATIVE["deliberately_avoided_defaults"],
        direction_id=str(direction["direction_id"]),
    )
    approval_request = sp.proposal.approval_request(proposal_record)
    report["proposal"] = {
        "proposal_id": proposal_record["proposal_id"],
        "user_visible_text": approval_request["text"],
        "proposal_digest": approval_request["proposal_digest"],
        "actions": approval_request["actions"],
        "internal_fields_leaked": [
            field for field in sp.proposal.INTERNAL_ONLY_FIELDS
            if field in approval_request["text"]
        ],
    }
    report["user_interface"] = sp.proposal.render_interface(proposal_record=proposal_record)
    step(
        "direction-proposal",
        f"proposal {proposal_record['proposal_id']}: "
        f"{len(approval_request['text'].splitlines())} lines a human reads; "
        f"{len(report['proposal']['internal_fields_leaked'])} internal fields leaked",
    )

    refusal = _attempt_before_approval(state, str(direction["direction_id"]))
    report["refusal_without_approval"] = refusal
    step("refusal-without-approval", f"planning refused before approval: {refusal[:120]}")

    design_module.approve_direction(
        state, str(direction["direction_id"]), identity=FIXTURE_APPROVER,
        note="AR-222D F1 vertical slice: explicit fixture approval through the real G1D gate",
    )
    approved = design_module.direction(state, str(direction["direction_id"])) or {}
    report["direction"]["status_after_approval"] = approved.get("status", "")
    report["direction"]["approved_revision"] = design_module.direction_revision(approved)
    approval = sp.proposal.approval_record(
        proposal_record, identity=FIXTURE_APPROVER,
        note="approved the exact text shown in the proposal",
    )
    approval_problems = sp.proposal.approval_problems(approval, proposal_record=proposal_record)
    report["approval"] = {
        "approver": approval["approver"],
        "authority": approval["authority"],
        "gate": approval["gate"],
        "channel": approval["channel"],
        "approval_id": approved.get("approval_id", ""),
        "approved_direction_revision": design_module.direction_revision(approved),
        "proposal_digest": approval["proposal_digest"],
        "approved_text_matches_shown_text": approval["approved_text"] == approval_request["text"],
        "proposal_digest_matches_shown_text": not approval_problems,
        "problems": approval_problems,
        "mechanism": "the real G1D gate; the status was not written directly",
    }
    report["interruptions"].append({
        "gate": "G1D",
        "reason": "design-direction approval",
        "after_direction_approval": False,
        "required": True,
    })
    step(
        "g1d-approval",
        f"approved by {FIXTURE_APPROVER} through G1D; approval {approved.get('approval_id', '')}",
    )

    # -- 8. continuation, without further interruption -------------------------
    continuations = (
        ("implementation planning", "compile an implementation plan from the approved direction"),
        ("component and primitive choice", "choose the component primitives the direction needs"),
        ("source provider choice", "select the registry and transport for those primitives"),
        ("capture planning", "plan what to render and at which viewports"),
        ("content-model refinement", "derive the per-surface content the plan must satisfy"),
        ("responsive mechanics", "decide the narrow-viewport behaviour"),
        ("typography candidate evaluation", "compare type candidates for tabular numerals"),
    )
    for kind, detail in continuations:
        tier = sp.interruption.classify(kind)
        report["interruptions"].append({
            "gate": "",
            "reason": kind,
            "after_direction_approval": bool(tier["interrupts_user"]),
            "tier": tier["tier"],
            "basis": tier["reason"][:140],
        })
    interrupting = [row for row in report["interruptions"] if row.get("after_direction_approval")]
    report["continuation"] = {
        "decisions_after_approval": len(continuations),
        "interruptions_after_approval": len(interrupting),
        "interruption_policy": sp.interruption.policy()["principle"],
        "policy_problems": sp.interruption.policy_problems(sp.interruption.policy()),
        "single_interruption_problems": sp.interruption.assert_single_interruption(report),
        "next_autonomous_step": "compile the design implementation plan from the approved direction",
    }
    step(
        "continuation",
        f"{len(continuations)} decisions taken after approval with {len(interrupting)} interruption(s)",
    )

    plan = _implementation_plan(state, direction, models)
    report["implementation_plan"] = {
        "plan_id": plan.get("plan_id", ""),
        "status": plan.get("status", ""),
        "constraints": len(plan.get("constraints") or []),
        "source_revision": plan.get("revision_hash", "")[:12],
    }
    step(
        "implementation-plan",
        f"plan {plan.get('plan_id', '')} compiled with {len(plan.get('constraints') or [])} constraints "
        "from the approved direction",
    )

    report["proof_readiness"] = _proof_readiness(state, direction)
    report["duration_seconds"] = round(time.monotonic() - clock, 3)
    report["failures"].extend(approval_problems)
    report["failures"].extend(report["continuation"]["single_interruption_problems"])
    report["completed"] = not report["failures"]
    return report


def _create_direction(state: dict, chosen: Mapping, models: Sequence[Mapping]) -> dict:
    """A real AR-202D direction record carrying the AR-222D specificity block."""
    from ... import design as design_module

    narrative = DIRECTION_NARRATIVE
    surfaces = "\n".join(
        f"- {model['surface']}: {model['surface_purpose']} "
        f"(rows {model['row_count']['low']}..{model['row_count']['high']}, "
        f"names {model['name_length']['low']}..{model['name_length']['high']} chars)"
        for model in models
    )
    record = design_module.create_direction(
        state,
        task_id=TASK_ID,
        goal=SLICE_REQUEST,
        scope="live timing surface; stint comparison surface; session setup surface",
        product_context=[f"[project] Formula 1 race operations: {DOMAIN}"],
        key_hierarchy=[
            "whether the race is on schedule is answerable in one glance from any point on the surface",
            f"{narrative['typography_intent']}",
            f"the content model, established before layout:\n{surfaces}",
        ],
        interaction_principles=[
            "no reading moves position between states",
            "no hover-dependent information, because a race engineer may be wearing gloves in a bright garage",
            "every destructive action states what it will affect before it takes effect",
        ],
        visual_principles=[
            f"{chosen['source_thing']} is the governing image: {chosen['ground_surface_character']}",
            f"{narrative['colour_intent']}",
            f"{narrative['layout_intent']}",
        ],
        content_principles=[
            f"{narrative['content_strategy']}",
            "no placeholder content: every surface models empty, loading and error states",
            "a retired or missing car never renumbers the cars still running",
        ],
        constraints=[
            "every numeric value carries its unit and its provenance",
            "the accent colour carries exactly three meanings: live flag, position gain, penalty",
            "no elevation is used; spacing carries all structure",
        ],
        existing_system=[
            "[project] from-scratch workspace; no existing design system is inherited",
        ],
        reference_findings_adopted=[
            "tabular numerals for any value read for its number rather than its label",
            "a fixed rail that does not reflow, so a reading keeps its position between states",
        ],
        findings_rejected=[
            "the broadcast-graphics candidate: strong typography but a weak product fit for an operating surface",
            "the cockpit-instrument candidate: not supportable at the required accessibility constraints",
            "a neon accent on near-black: rejected because it carries no semantic load in this domain",
        ],
        accessibility_requirements=[
            "every state change is conveyed by text as well as by motion",
            "target contrast for a reading read at a glance under pit-lane glare",
            "no information available only through hover or pointer movement",
        ],
        responsive_requirements=[
            "the primary timing rail keeps its positions at every viewport; it does not reflow",
            "below the desktop width the secondary surfaces stack in a fixed order, and the timing rail "
            "remains readable rather than horizontally scrolling",
        ],
        approved_deviations=[
            f"richness comes from {chosen['richness_source']} rather than from imagery or illustration; "
            "a race timing surface has no honest imagery to add",
        ],
    )
    record["requirement_ids"] = [f"req-{model['surface']}" for model in models]
    _record_requirements(state, record, models)
    record["ar222d_specificity"] = {
        "grammar_id": sp.GRAMMAR_ID,
        "concept_id": str(chosen["concept_id"]),
        "concept_family": str(chosen["family"]),
        "source_thing": str(chosen["source_thing"]),
        "hierarchy_model": str(chosen["hierarchy_model"]),
        "richness_source": str(chosen["richness_source"]),
        "motion_intent": str(DIRECTION_NARRATIVE["motion_intent"]),
        "own_failure_mode": str(chosen["own_failure_mode"]),
        "deliberately_avoided_defaults": list(DIRECTION_NARRATIVE["deliberately_avoided_defaults"]),
        "role_bindings": [dict(row) for row in ROLE_BINDINGS],
        "content_model_ids": [str(model["content_model_id"]) for model in models],
        "platform_profile": "web",
        "platform_bound": False,
        "alternatives_held_secondary": True,
    }
    return record


def _record_requirements(state: dict, direction: Mapping, models: Sequence[Mapping]) -> None:
    """One requirement per surface, derived from its content model.

    Proof-readiness needs a requirement *identity* that a finding can cite, and a
    requirement whose id exists nowhere else is not an identity. Deriving them from the
    content model keeps them honest: each states what the surface must support, including
    the states that break naive layouts.
    """
    import hashlib

    for model in models:
        statement = (
            f"{model['surface']} must support {model['surface_purpose']} at "
            f"{model['row_count']['low']}-{model['row_count']['high']} rows, with names up to "
            f"{model['name_length']['high']} characters, and must design its empty, loading and "
            "error states rather than defaulting them"
        )
        state.setdefault("design_requirements", []).append({
            "record_id": contracts.new_record_id("drq"),
            "requirement_id": f"req-{model['surface']}",
            "task_id": TASK_ID,
            "direction_id": str(direction.get("direction_id", "")),
            "statement": statement,
            "surface": str(model["surface"]),
            "content_model_id": str(model["content_model_id"]),
            "edge_content_count": len(model.get("edge_content") or []),
            "state": "implemented",
            # Hashed locally rather than through contracts.digest_fields, which accepts only
            # registered approval subject types. A requirement revision is not a gated subject,
            # and inventing a subject type for it would put one on the same footing as G1D.
            "revision_hash": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
            "recorded_at": contracts.utc_now(),
        })


def _attempt_before_approval(state: Mapping, direction_id: str) -> str:
    """Planning before approval must be refused, through the real check."""
    from ... import design as design_module

    return "; ".join(design_module.direction_problems(state, task_id=TASK_ID)) or (
        "the direction was already approved, so this refusal is vacuous and the test is not meaningful"
    )


def _implementation_plan(state: dict, direction: Mapping, models: Sequence[Mapping]) -> dict:
    """A plan record carrying the content-before-layout ordering explicitly.

    Constraints are *derived* from the approved direction and the content model rather
    than written here, because the point of this slice is that the layout inherits its
    obligations from content it has already described. A plan whose constraints were
    hardcoded in the test would prove nothing about content-before-layout.
    """
    specificity = direction.get("ar222d_specificity") if isinstance(
        direction.get("ar222d_specificity"), Mapping
    ) else {}
    constraints: list[dict] = []
    for model in models:
        for text in sp.content.layout_constraints(model):
            constraints.append({
                "constraint_id": contracts.new_record_id("cnx"),
                "surface": str(model["surface"]),
                "basis": "CONTENT_MODEL",
                "statement": text,
                "source_content_model_id": str(model["content_model_id"]),
            })
    bindings, _problems = sp.grammar.role_bindings(specificity.get("role_bindings") or ())
    for binding in bindings:
        constraints.append({
            "constraint_id": contracts.new_record_id("cnx"),
            "surface": "all",
            "basis": "DIRECTION_ROLE",
            "statement": (
                f"{binding['role_kind']} role {binding['role']}: {binding['meaning']}"
            ),
            "value": binding["value"],
        })
    for avoided in (specificity.get("deliberately_avoided_defaults") or ()):
        constraints.append({
            "constraint_id": contracts.new_record_id("cnx"),
            "surface": "all",
            "basis": "AVOIDED_DEFAULT",
            "statement": f"the approved direction avoids {avoided}",
        })
    plan = {
        "plan_id": contracts.new_record_id("dip"),
        "direction_id": str(direction["direction_id"]),
        "task_id": TASK_ID,
        "status": "READY",
        "requirements": [str(item) for item in (direction.get("requirement_ids") or ())],
        "constraints": constraints,
        "revision_hash": contracts.direction_fingerprint(direction),
        "recorded_at": contracts.utc_now(),
    }
    plan["content_model"] = dict(models[0])
    plan["content_model_established_at_step"] = 1
    plan["layout_decided_at_step"] = 6
    plan["planned_at"] = contracts.utc_now()
    plan["content_layout_problems"] = sp.content.content_layout_precedence(plan)
    state.setdefault("design_implementation_plans", []).append(plan)
    return plan


def _proof_readiness(state: Mapping, direction: Mapping) -> dict:
    from ...rendered_critique import proof as proof_module

    report = proof_module.proof_report(state)
    return {
        "requirements": report["requirements"],
        "gaps": len(report["gaps"]),
        "orphans": len(report["orphans"]),
        "absent_roles": report["absent_roles"],
        "verdicts": report["verdicts"],
        "note": report["verdict_note"],
        "fields_available": {
            field: True for field in proof_module.PROOF_FIELDS
        } if report["requirements"] else {},
        "pre_problems": proof_module.proof_problems(state),
    }


def describe(report: Mapping) -> str:
    lines = [
        "AR-222D F1 VERTICAL SLICE",
        "",
        f"request: {report.get('request', '')}",
        f"completed: {report.get('completed', False)}",
        f"duration: {report.get('duration_seconds', 0)}s",
        "",
        "steps:",
    ]
    for row in report.get("steps") or []:
        lines.append(f"  {row.get('step', '')}: {row.get('detail', '')}")
    proposal = report.get("proposal") or {}
    if proposal.get("user_visible_text"):
        lines.extend(["", "the user saw:", "", proposal["user_visible_text"]])
    interface = report.get("user_interface")
    if interface:
        lines.extend(["", "the full exchange:", "", interface])
    failures = report.get("failures") or []
    if failures:
        lines.extend(["", "failures:"])
        lines.extend(f"  - {item}" for item in failures)
    return "\n".join(lines)


__all__ = [
    "DOMAIN",
    "FIXTURE_APPROVER",
    "SLICE_REQUEST",
    "TASK_ID",
    "concept_records",
    "content_models",
    "describe",
    "run",
]
