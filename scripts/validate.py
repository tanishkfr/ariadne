#!/usr/bin/env python3
"""
Builder OS validation harness.

check.py verifies the Builder OS repository. THIS verifies a validation RUN:
the project Builder OS produced, and the run record you kept while producing it.

  python scripts/validate.py --run validation/runs/A1.md
  python scripts/validate.py --run validation/runs/A1.md --project ../my-project
  python scripts/validate.py --benchmark
  python scripts/validate.py --self-test

Deliberately absent: any design-quality score, any composite number, anything
that would let a good-looking run substitute for a good project. Metrics here
are counts of FAILURES (B-questions, wrong routes, unnecessary documents) --
the incentive points at improving the system, not at inflating a score.
Value and friction stay human-judged and are never aggregated.
"""

import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(ROOT, "validation", "runs")

# Canonical source: ROUTER.md section 6. Duplicated here because a script
# cannot read prose. check_mode_drift() below fails if these diverge from modes/.
REQUIRED_DOCS = {
    "client-or-portfolio": ["PROJECT.md", "DESIGN.md", "HANDOFF.md", "QA.md"],
    "product-app":         ["PROJECT.md", "ARCHITECTURE.md", "DESIGN.md", "HANDOFF.md", "QA.md"],
    "game-experiment":     ["PROJECT.md", "DESIGN.md"],
    "content-system":      ["PROJECT.md", "CONTENT-LEARNINGS.md"],
    "audit-review":        ["QA.md"],
}
# Conditional documents whose creation is a signal worth watching -- each one
# should have been triggered by a stated rule, not by habit. AGENTS.md is
# deliberately absent: it is the runtime state file and is always expected.
CONDITIONAL_DOCS = ["ARCHITECTURE.md", "TASKS.md", "ASSETS.md", "RESEARCH.md",
                    "RETROSPECTIVE.md", "CONTENT-LEARNINGS.md"]

VALID_STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
VALID_GATES = ["none", "G1", "G2", "G3", "G4", "G5"]
VALID_RESULTS = ["PASS", "PARTIAL", "FAIL", "UNPROVEN"]
EVENT_TYPES = ["VALUE", "FRICTION", "FAILURE", "DECISION", "INTERVENTION",
               "RESTART", "GATE", "QUESTION", "DEVIATION"]
QUESTION_CLASSES = ["A", "B", "C"]

RUN_SECTIONS = ["## Run", "## Baseline", "## Events", "## Metrics", "## Report"]
RUN_FIELDS = ["Run ID", "Date", "Builder OS version", "Test", "Mode",
              "Provider", "Model", "Result"]


# ---------------------------------------------------------------- helpers

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def field(text, name):
    """Pull `| **Name** | value |` or `- **Name:** value` out of a run file."""
    m = re.search(r"\|\s*\*\*" + re.escape(name) + r"\*\*\s*\|([^|\n]*)\|", text)
    if m:
        return m.group(1).strip().strip("`")
    m = re.search(r"\*\*" + re.escape(name) + r":?\*\*[:\s]*([^\n|]+)", text)
    return m.group(1).strip().strip("`") if m else ""


def parse_events(text):
    """
    Events are pipe rows under ## Events:
      | TYPE | stage | description | evidence | expected? | importance |
    Returns list of dicts. Malformed rows are returned with _bad set.
    """
    events = []
    section = re.search(r"##\s+Events(.*?)(?=\n##\s|\Z)", text, re.S)
    if not section:
        return events
    for line in section.group(1).split("\n"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|--") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        etype = cells[0].strip("*` ").upper()
        if etype in ("TYPE", ""):
            continue
        ev = {
            "type": etype,
            "stage": cells[1],
            "desc": cells[2],
            "evidence": cells[3],
            "raw": line,
            "_bad": etype not in EVENT_TYPES,
        }
        # QUESTION events carry a class marker somewhere in the row
        if etype == "QUESTION":
            cm = re.search(r"\bclass\s*[:=]?\s*([ABC])\b", line, re.I)
            ev["qclass"] = cm.group(1).upper() if cm else None
        events.append(ev)
    return events


# ---------------------------------------------------------------- checks

def check_mode_drift():
    """The mode list here must match modes/ or the required-doc map is stale."""
    problems = []
    modes_dir = os.path.join(ROOT, "modes")
    if not os.path.isdir(modes_dir):
        return ["modes/ directory missing"]
    on_disk = {f[:-3] for f in os.listdir(modes_dir) if f.endswith(".md")}
    known = set(REQUIRED_DOCS)
    for m in on_disk - known:
        problems.append(f"mode '{m}' exists but has no required-doc mapping here")
    for m in known - on_disk:
        problems.append(f"required-doc mapping references deleted mode '{m}'")
    return problems


def check_run_file(text, path):
    """Structure of the run record itself."""
    problems = []
    name = os.path.basename(path)

    for sec in RUN_SECTIONS:
        if sec not in text:
            problems.append(f"{name}: missing section {sec}")

    for f in RUN_FIELDS:
        if not field(text, f):
            problems.append(f"{name}: field '{f}' is empty or missing")

    result = field(text, "Result").upper()
    if result and result not in VALID_RESULTS:
        problems.append(f"{name}: Result '{result}' not one of {VALID_RESULTS}")

    # An unfilled template must not be mistaken for a real run.
    if "<" in field(text, "Run ID") or field(text, "Run ID").lower() == "id":
        problems.append(f"{name}: Run ID is still a placeholder")

    events = parse_events(text)
    for ev in events:
        if ev["_bad"]:
            problems.append(f"{name}: unknown event type '{ev['type']}'")
        if not ev["evidence"] or ev["evidence"].startswith("<"):
            problems.append(f"{name}: {ev['type']} event has no evidence reference")
        if ev["type"] == "QUESTION" and ev.get("qclass") not in QUESTION_CLASSES:
            problems.append(
                f"{name}: QUESTION event missing class A/B/C -- "
                f"the B-count is the primary handoff metric and cannot be derived without it"
            )

    # Baseline must be captured, and for Test A it must be captured FIRST or
    # it is contaminated by having seen the Builder OS output.
    if "## Baseline" in text:
        bl = re.search(r"##\s+Baseline(.*?)(?=\n##\s|\Z)", text, re.S)
        body = bl.group(1) if bl else ""
        if len(body.split()) < 20:
            problems.append(f"{name}: Baseline section is empty -- "
                            f"without it the run cannot show what changed")
        if "captured before" not in body.lower() and "before running" not in body.lower():
            problems.append(f"{name}: Baseline does not state it was captured "
                            f"BEFORE the run -- a baseline written afterwards is not a control")

    return problems, events


def check_project(project, expected_mode, expected_stage):
    """The project directory Builder OS produced."""
    problems, observations = [], {}
    if not os.path.isdir(project):
        return [f"project path not found: {project}"], observations

    present = {f for f in os.listdir(project) if f.endswith(".md")}
    observations["documents_present"] = sorted(present)

    required = REQUIRED_DOCS.get(expected_mode)
    if required is None:
        problems.append(f"unknown mode '{expected_mode}'")
        return problems, observations

    missing = [d for d in required if d not in present]
    if missing:
        problems.append(f"required documents missing for {expected_mode}: {missing}")

    # Unnecessary ceremony is a real failure mode -- a document nobody needs
    # is worse than none, because it manufactures the appearance of process.
    unexpected = [d for d in present
                  if d not in required and d in CONDITIONAL_DOCS]
    observations["conditional_documents_created"] = unexpected

    agents = os.path.join(project, "AGENTS.md")
    if not os.path.exists(agents):
        problems.append("AGENTS.md missing -- a fresh session cannot locate the project")
    else:
        a = read(agents)
        if "## Current state" not in a:
            problems.append("AGENTS.md has no '## Current state'")
        stage = field(a, "Stage")
        gate = field(a, "Last gate passed")
        nxt = field(a, "Next prompt")
        observations["state_stage"] = stage
        observations["state_gate"] = gate
        observations["state_next_prompt"] = nxt

        if stage and stage not in VALID_STAGES:
            problems.append(f"AGENTS.md Stage '{stage}' is not a valid stage")
        if gate and gate not in VALID_GATES:
            problems.append(f"AGENTS.md Last gate '{gate}' is not a valid gate")
        if expected_stage and stage and stage != expected_stage:
            problems.append(f"state drift: AGENTS.md says {stage}, run says {expected_stage}")
        if nxt and not nxt.startswith("<"):
            target = os.path.join(ROOT, nxt)
            if nxt.lower() != "none" and not os.path.exists(target):
                problems.append(f"Next prompt points at a file that does not exist: {nxt}")

    # Never-commit check, cheap and high consequence
    for bad in [".env", ".env.local", "id_rsa", "credentials.json"]:
        if os.path.exists(os.path.join(project, bad)):
            problems.append(f"SECRET RISK: {bad} present in project root")

    return problems, observations


def compute_metrics(events, observations):
    """Counts only. No composite score, by design."""
    q = [e for e in events if e["type"] == "QUESTION"]
    return {
        "MEASURED  b_class_questions": sum(1 for e in q if e.get("qclass") == "B"),
        "MEASURED  a_class_questions": sum(1 for e in q if e.get("qclass") == "A"),
        "MEASURED  c_class_questions": sum(1 for e in q if e.get("qclass") == "C"),
        "MEASURED  failures": sum(1 for e in events if e["type"] == "FAILURE"),
        "MEASURED  deviations": sum(1 for e in events if e["type"] == "DEVIATION"),
        "MEASURED  interventions": sum(1 for e in events if e["type"] == "INTERVENTION"),
        "MEASURED  restarts": sum(1 for e in events if e["type"] == "RESTART"),
        "MEASURED  gates_crossed": sum(1 for e in events if e["type"] == "GATE"),
        "OBSERVED  conditional_docs": len(observations.get("conditional_documents_created", [])),
        "HUMAN     value_events": sum(1 for e in events if e["type"] == "VALUE"),
        "HUMAN     friction_events": sum(1 for e in events if e["type"] == "FRICTION"),
    }


# ---------------------------------------------------------------- modes

def run_check(run_path, project, expected_stage):
    print(f"RUN  {run_path}")
    text = read(run_path)
    problems, events = check_run_file(text, run_path)
    observations = {}

    mode = field(text, "Mode")
    if project:
        p2, observations = check_project(project, mode, expected_stage)
        problems += p2

    drift = check_mode_drift()
    problems += drift

    print()
    if observations:
        print("OBSERVATIONS")
        for k, v in observations.items():
            print(f"  {k}: {v}")
        print()

    metrics = compute_metrics(events, observations)
    print("METRICS")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    b = metrics["MEASURED  b_class_questions"]
    print(f"\n  B-class handoff re-derivations: {b}  (target <= 2)  "
          f"{'PASS' if b <= 2 else 'OVER TARGET'}")
    print("\n  No composite score is produced. Value and friction are human-judged")
    print("  and deliberately not aggregated -- a number there would reward writing")
    print("  more events rather than building better projects.")

    print()
    if problems:
        print(f"FAIL  {len(problems)} problem(s)")
        for p in problems:
            print(f"        {p}")
        return 1
    print("ok    run record and project structure valid")
    return 0


def benchmark():
    files = sorted(glob.glob(os.path.join(RUNS_DIR, "*.md")))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    if not files:
        print("No runs yet. Copy validation/run-template.md into validation/runs/ "
              "and fill it in as you go.")
        return 0
    rows = []
    for f in files:
        t = read(f)
        ev = parse_events(t)
        m = compute_metrics(ev, {})
        rows.append({
            "run": field(t, "Run ID") or os.path.basename(f)[:-3],
            "test": field(t, "Test"),
            "ver": field(t, "Builder OS version"),
            "prov": field(t, "Provider"),
            "model": field(t, "Model"),
            "result": field(t, "Result"),
            "B": m["MEASURED  b_class_questions"],
            "fail": m["MEASURED  failures"],
            "dev": m["MEASURED  deviations"],
            "int": m["MEASURED  interventions"],
            "val": m["HUMAN     value_events"],
            "fric": m["HUMAN     friction_events"],
        })
    hdr = f"{'RUN':<8}{'TEST':<8}{'VER':<9}{'PROVIDER':<10}{'MODEL':<12}{'RESULT':<10}{'B':>3}{'FAIL':>5}{'DEV':>5}{'INT':>5}{'VAL':>5}{'FRIC':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['run']:<8}{r['test']:<8}{r['ver']:<9}{r['prov']:<10}{r['model']:<12}"
              f"{r['result']:<10}{r['B']:>3}{r['fail']:>5}{r['dev']:>5}{r['int']:>5}"
              f"{r['val']:>5}{r['fric']:>6}")
    print(f"\n{len(rows)} run(s). B = handoff re-derivations (target <=2).")
    print("VAL/FRIC are human-judged counts -- compare them as narrative, never as a score.")
    return 0


def self_test():
    """
    Every guard must be able to fail. A check that cannot fail is not evidence.
    Builds deliberately broken inputs in memory and asserts each guard fires.
    """
    cases = []

    base = read(os.path.join(ROOT, "validation", "run-template.md"))

    def expect(name, text, needle):
        probs, _ = check_run_file(text, "probe.md")
        hit = any(needle.lower() in p.lower() for p in probs)
        cases.append((name, hit))

    expect("missing section", base.replace("## Events", "## Stuff"), "missing section")
    expect("bad result value", base.replace("| **Result** | `<PASS", "| **Result** | `BANANA"), "not one of")
    expect("unknown event type",
           base.replace("| VALUE |", "| SPARKLE |", 1), "unknown event type")
    expect("question without class",
           base.replace("class B", "no class here", 1), "missing class")
    expect("baseline not pre-captured",
           re.sub(r"captured before", "written up later", base, flags=re.I), "captured")

    # placeholder run id must not pass as a real run
    expect("placeholder run id", base, "placeholder")

    # project guards
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        probs, _ = check_project(d, "game-experiment", "S3")
        cases.append(("missing required docs", any("required documents missing" in p for p in probs)))
        cases.append(("missing AGENTS.md", any("AGENTS.md missing" in p for p in probs)))

        open(os.path.join(d, "PROJECT.md"), "w").write("x")
        open(os.path.join(d, "DESIGN.md"), "w").write("x")
        open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8").write(
            "## Current state\n\n| **Stage** | `S9` |\n| **Last gate passed** | `G9` |\n"
            "| **Next prompt** | `prompts/nope.md` |\n")
        probs, _ = check_project(d, "game-experiment", "S3")
        cases.append(("invalid stage", any("not a valid stage" in p for p in probs)))
        cases.append(("invalid gate", any("not a valid gate" in p for p in probs)))
        cases.append(("state drift", any("state drift" in p for p in probs)))
        cases.append(("dangling next prompt", any("does not exist" in p for p in probs)))

        open(os.path.join(d, ".env"), "w").write("SECRET=1")
        probs, _ = check_project(d, "game-experiment", "S3")
        cases.append(("secret in project root", any("SECRET RISK" in p for p in probs)))

    print("SELF-TEST  -- every guard must be able to fail\n")
    ok = True
    for name, fired in cases:
        print(f"  {'ok  ' if fired else 'DEAD'}  {name}")
        ok &= fired
    print()
    if ok:
        print(f"PASS  {len(cases)} guards all fail correctly on broken input")
        return 0
    print("FAILED  one or more guards cannot fail -- they are not evidence")
    return 1


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        return self_test()
    if "--benchmark" in args:
        return benchmark()
    if "--run" in args:
        run_path = args[args.index("--run") + 1]
        project = args[args.index("--project") + 1] if "--project" in args else None
        stage = args[args.index("--stage") + 1] if "--stage" in args else None
        return run_check(run_path, project, stage)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
