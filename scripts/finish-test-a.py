#!/usr/bin/env python3
"""
Ariadne -- Test A collection.

Run after Codex has finished. Validates the project and the run record,
generates RESULT.md, and updates the benchmark.

    python scripts/finish-test-a.py
    python scripts/finish-test-a.py --run validation/runs/A1

Reuses scripts/validate.py entirely -- this is a wrapper, not a second
validation system. It reports what happened. It does not judge whether the
work is good, and it produces no score.
"""

import os
import re
import sys
import glob
import datetime
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(ROOT, "validation", "runs")

spec = importlib.util.spec_from_file_location("bosvalidate",
                                              os.path.join(ROOT, "scripts", "validate.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)

BAR = "-" * 64


def latest_run():
    dirs = [d for d in glob.glob(os.path.join(RUNS_DIR, "A*"))
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "run.md"))]
    if not dirs:
        print("\nNo Test A run found. Run this first:\n\n    python scripts/setup-test-a.py\n")
        sys.exit(1)
    return sorted(dirs, key=lambda d: int(re.sub(r"\D", "", os.path.basename(d)) or 0))[-1]


def project_from_run(text):
    m = re.search(r"^>\s*Project:\s*`([^`]+)`", text, re.M)
    return m.group(1) if m else None


def capture(text, header):
    m = re.search(r"###\s+" + re.escape(header) + r"(.*?)(?=\n###\s|\n##\s|\n>\s*Project:|\Z)",
                  text, re.S)
    return m.group(1).strip() if m else ""


def strip_guidance(section):
    """
    Drop instructional blockquotes so the report shows what the human wrote
    rather than replaying the template's own advice back at them.
    """
    return "\n".join(l for l in section.split("\n")
                     if not l.lstrip().startswith(">")).strip()


def filled(section):
    """A section still full of <placeholders> has not been filled in."""
    return len(V.prose(section).split()) > 8


# ------------------------------------------------------- transcript extraction
#
# The Strategist prompt SPECIFIES the shape of the reply: a named FRAME, a Mode
# line with a confidence, and a closing NEXT block. That contract is what makes
# extraction honest rather than guesswork -- we are reading a format the frozen
# prompt demanded, not pattern-matching hopefully.
#
# The contract is READ FROM prompts/project-start.md, never restated here, so it
# cannot drift away from the prompt the user actually pasted.

START_PROMPT = os.path.join(ROOT, "prompts", "project-start.md")


def frame_keys():
    """The FRAME field names, taken from the frozen prompt."""
    text = V.read(START_PROMPT)
    m = re.search(r"FRAME[^\n]*\n(.*?)\n\s*\n", text, re.S)
    if not m:
        return []
    return re.findall(r"^\s{2,}([A-Z]{4,12})\s{2,}\S", m.group(1), re.M)


def block_keys():
    """
    The ROUTING BLOCK field names, from the frozen prompt.

    This matters more than the FRAME. The prompt says "FRAME - fill these
    before deciding anything" -- that is internal reasoning, and a session is
    free not to print it. STEP 3 is what it must actually EMIT. So `Unresolved`
    is the reliable ambiguity signal; OBJECT is a bonus when it appears.
    """
    text = V.read(START_PROMPT)
    m = re.search(r"^ROUTING BLOCK\n(.*?)\n\s*\n", text, re.S | re.M)
    if not m:
        return []
    return [l.split(":")[0].strip() for l in m.group(1).split("\n") if ":" in l]


def next_contract():
    """The lines the prompt requires the reply to end with."""
    text = V.read(START_PROMPT)
    m = re.search(r"END YOUR RESPONSE WITH THIS[^\n]*\n(.*?)\n\s*\nNever end", text, re.S)
    if not m:
        return []
    return [re.match(r"\s*([A-Za-z][^:]*):", l).group(1).strip()
            for l in m.group(1).split("\n")
            if re.match(r"\s*([A-Za-z][^:]*):", l)]


# A reply is prose, and the label may arrive wearing markdown: a bullet, bold,
# a table cell, or the prompt's own indented FRAME layout. All of these are the
# same contract, so all of them must read. Anything genuinely absent stays
# absent -- tolerance here is about formatting, never about guessing content.
LABEL = (r"^[ \t]*(?:[-*+][ \t]*)?"        # optional bullet
         r"(?:\|[ \t]*)?"                  # optional leading table pipe
         r"\*{0,2}`?%s`?\*{0,2}"           # the label, optionally bold/code
         r"[ \t]*(?:[:\-\|]|[ \t]{2,})[ \t]*"   # : - | or column whitespace
         r"(.+?)[ \t]*\|?[ \t]*$")         # value, optional trailing pipe


def clean(v):
    """Strip markdown decoration from an extracted value."""
    return re.sub(r"^[\*`_ ]+|[\*`_ ]+$", "", v.strip()).strip()


def extract_routing(transcript):
    """
    Pull the routing decision out of the raw Codex reply. Returns
    {key: (value, True)} for what was found; absent keys are simply absent --
    nothing is inferred, and nothing is invented when the format was not met.
    """
    out = {}
    for key in frame_keys():
        m = re.search(LABEL % key, transcript, re.M)
        if m:
            out[key] = clean(m.group(1))

    for key in block_keys():
        m = re.search(LABEL % re.escape(key), transcript, re.M)
        if m:
            out["BLOCK::" + key] = clean(m.group(1))

    m = re.search(LABEL % "Mode", transcript, re.M)
    if m:
        out["MODE"] = clean(m.group(1))
    m = re.search(r"confidence\s*[:=]?\s*(High|Medium|Low)", transcript, re.I)
    if m:
        out["CONFIDENCE"] = m.group(1).capitalize()

    qs = re.findall(r"^\s*(?:Question|Questions)\s*[:\-]\s*(.*)$", transcript, re.M | re.I)
    body = re.search(r"^\s*Questions?\s*[:\-]\s*(.*?)(?=\n\s*\n)", transcript, re.M | re.S | re.I)
    if body:
        qs = [q for q in [body.group(1).strip()] if q]
    if qs:
        out["QUESTION"] = qs[0].strip()

    for label in next_contract():
        m = re.search(r"^\s*" + re.escape(label) + r"\s*:\s*(.*)$", transcript, re.M)
        if m:
            out["NEXT::" + label] = m.group(1).strip()
    return out


def derive_deviations(r, docs=None):
    """
    Compare the reply against the contract the prompt stated. Each item names
    the rule it violates, so a finding can be traced rather than asserted.
    Returns (deviations, confirmations).
    """
    dev, ok = [], []
    if not r:
        return dev, ok

    obj = r.get("OBJECT", "")
    unres = r.get("BLOCK::Unresolved", "")
    conf = r.get("CONFIDENCE", "")

    # Ambiguity can be signalled two ways: the FRAME's OBJECT (printed only if
    # the session chose to show its reasoning) or the ROUTING BLOCK's
    # Unresolved field (mandatory output). Either counts.
    ambiguous = ("UNRESOLVED" in obj.upper()
                 or bool(unres and not re.match(r"none|nothing|n/?a\b", unres, re.I)))

    # R-DEST-1: an unresolved object means LOW, however clear everything else is.
    if ambiguous:
        if conf and conf != "Low":
            dev.append(f"R-DEST-1: the object is unresolved but confidence is "
                       f"{conf}, not Low")
        elif conf == "Low":
            ok.append("R-DEST-1 held: an unresolved object produced Low confidence")

    # Low confidence => STOP and ask. "Stop" is about not PROCEEDING, not about
    # refusing to name a mode: STEP 3 requires the line "Mode: <mode>
    # (confidence: ...)", and the prompt explicitly says to pick the closest
    # workflow and say so. Naming a closest fit while flagging Low and asking is
    # compliance, so it is measured by what the session DID, not what it called
    # the mode.
    if conf == "Low":
        if r.get("QUESTION") or r.get("BLOCK::Questions"):
            ok.append("a clarifying question was asked, as Low confidence requires")
        else:
            dev.append("confidence is Low but no clarifying question was found")

        wrote = [d for d in (docs or []) if d != "AGENTS.md"]
        if wrote:
            dev.append(f"confidence is Low but documents were written anyway: "
                       f"{wrote} -- the prompt says STOP and ask before committing")
        elif docs is not None:
            ok.append("Low confidence stopped before writing documents")

    # The closing NEXT block is mandatory and has named fields.
    for label in next_contract():
        if "NEXT::" + label in r:
            ok.append(f"NEXT block field present: '{label}'")
        else:
            dev.append(f"NEXT block is missing the required field '{label}'")
    return dev, ok


def routing_section(routing, dev, ok, transcript):
    """The automatically-derived half of the report."""
    if not transcript:
        return ("### Routing — NOT EXTRACTED\n\n"
                "_No transcript at `evidence/transcript.md`. Paste the Codex reply there and\n"
                "re-run; routing is the primary measurement of Test A and everything below\n"
                "falls back to whatever was typed in by hand._\n")
    if not routing:
        return ("### Routing — NOT EXTRACTED\n\n"
                f"_A transcript exists (`{transcript}`) but none of the FRAME fields the prompt\n"
                "specifies were found in it. **That is itself a finding**: either the reply did\n"
                "not follow the required format, or the wrong text was pasted._\n")

    def cell(v):
        return v.splitlines()[0][:90].replace("|", "\\|")

    frame = [k for k in frame_keys() if k in routing]
    rows = [f"| `{k}` | {cell(routing[k])} |" for k in frame]
    rows += [f"| `{k}` | {cell(routing['BLOCK::' + k])} |"
             for k in block_keys() if "BLOCK::" + k in routing and k != "Mode"]
    rows.append(f"| **Mode** | {cell(routing.get('MODE', '_not stated_'))} |")
    rows.append(f"| **Confidence** | **{routing.get('CONFIDENCE', '_not stated_')}** |")
    rows.append(f"| **Question asked** | {cell(routing.get('QUESTION', '_none found_'))} |")
    out = ("### Routing — extracted from the transcript\n\n"
           f"_Read mechanically from `{transcript.replace(os.sep, '/')}` using the format "
           "`prompts/project-start.md` requires. Reproducible._\n\n"
           "| Field | Value |\n|---|---|\n" + "\n".join(rows) + "\n\n")

    # An absent FRAME must be stated, not silently omitted -- a shorter table
    # looked identical to a complete one in the A2 report, and R-DEST-1 had in
    # fact gone unchecked.
    if not frame:
        out += ("> **The FRAME was not printed.** The prompt treats it as internal "
                "(\"fill these before deciding\"), so this is not a deviation — but it "
                "means `OBJECT` could not be read directly, and the ambiguity check "
                "fell back to the ROUTING BLOCK's `Unresolved` field"
                + ("." if "BLOCK::Unresolved" in routing else
                   ", **which is also absent — so R-DEST-1 could not be checked at all.**")
                + "\n\n")

    out += "### Contract check\n\n"
    out += ("_Each line names the rule it tests. Derived from the prompt, not judged._\n\n")
    for o in ok:
        out += f"- **held** — {o}\n"
    for d in dev:
        out += f"- **DEVIATION** — {d}\n"
    if not dev:
        out += "\nNo deviations from the stated contract. "
        out += "Empty is a valid and good result.\n"
    return out


def learned(routing, dev, problems, events):
    """
    Facts only. This section must never editorialise -- the moment it starts
    grading the run it becomes the composite score this harness refuses to have.
    """
    lines = []
    if routing:
        conf = routing.get("CONFIDENCE")
        obj = routing.get("OBJECT", "")
        if conf and "UNRESOLVED" in obj.upper():
            lines.append(f"An unresolved OBJECT produced **{conf}** confidence and "
                         f"{'a question instead of a mode' if routing.get('QUESTION') else 'no question'}. "
                         f"This is the behaviour Test A exists to check.")
        if routing.get("NEXT::NEXT"):
            lines.append(f"The session chained forward: NEXT pointed at "
                         f"`{routing['NEXT::NEXT']}`.")
    lines.append(f"{len(dev)} contract deviation(s) and {len(problems)} structural "
                 f"problem(s) were found mechanically.")
    lines.append(f"{len(events)} event(s) were logged by hand during the run.")
    if not events:
        lines.append("**No events were logged.** Friction and value are invisible to the "
                     "harness unless written down while they happen.")
    return "\n".join(f"- {l}" for l in lines)


def build_result(run_id, run_file, project, problems, events, observations, metrics,
                 routing=None, dev=(), ok=(), transcript=None):
    text = V.read(run_file)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    routing_manual = capture(text, "Routing result")
    docs = capture(text, "Documents Ariadne created")
    state = capture(text, "Runtime state after the run")
    devs = capture(text, "Deviations from documented behaviour")
    comp = capture(text, "The comparison")
    # Stop at the "After the run" subsection: that is the comparison, not the
    # baseline, and including it made the report print the same empty table twice.
    baseline = re.search(r"##\s+Baseline(.*?)(?=\n###\s|\n##\s|\Z)", text, re.S)
    baseline = strip_guidance(baseline.group(1)) if baseline else ""

    def evs(kind):
        rows = [e for e in events if e["type"] == kind]
        if not rows:
            return "_None recorded. Empty is a valid result._"
        return "\n".join(f"- **{e['stage']}** — {e['desc']}  ·  `{e['evidence']}`" for e in rows)

    q = [e for e in events if e["type"] == "QUESTION"]
    b = metrics["MEASURED  b_class_questions"]

    out = f"""# TEST A RESULT — {run_id}

> Generated by `scripts/finish-test-a.py` on {now}. Regenerating overwrites this file;
> the run record is the source of truth.

**Project:** `{project or "not recorded"}`
**Run record:** `{os.path.relpath(run_file, ROOT)}`

The four sections below are **never collapsed into one number.** They are different
kinds of evidence and mixing them would hide which is which.

---

## PROVEN

*Deterministic. Derived from files by the checker. Reproducible.*

| Check | Result |
|---|---|
| Run record + project structure | {"**FAIL** — see below" if problems else "**PASS**"} |
| Documents present | `{observations.get("documents_present", "not checked")}` |
| Conditional documents created | `{observations.get("conditional_documents_created", [])}` |
| Runtime stage | `{observations.get("state_stage", "—")}` |
| Last gate passed | `{observations.get("state_gate", "—")}` |
| Next prompt | `{observations.get("state_next_prompt", "—")}` |

### Counts

| Metric | Value |
|---|---|
"""
    for k, v in metrics.items():
        cls, name = k.split(None, 1)
        out += f"| {name.strip()} _{cls}_ | {v} |\n"

    out += f"""
**Handoff re-derivations (B-class): {b}** — target ≤2. {"PASS" if b <= 2 else "OVER TARGET"}

*Test A ends before a handoff, so a B-count of 0 here means "not exercised", not "perfect".*
"""

    if problems:
        out += "\n### Structural problems\n\n" + "\n".join(f"- {p}" for p in problems) + "\n"

    out += f"""
---

## OBSERVED

*What actually happened. Real, but not reproducible.*

{routing_section(routing, dev, ok, transcript)}

### Routing, as recorded by hand

{routing_manual if filled(routing_manual) else "_Not filled in — the extracted table above supersedes it._"}

### Documents

{docs if filled(docs) else "_Not filled in._"}

### Runtime state

{state if filled(state) else "_Not filled in._"}

### Deviations from documented behaviour

{devs if filled(devs) else "_None recorded._"}

### Friction

{evs("FRICTION")}

### Value

{evs("VALUE")}

### Questions asked

{chr(10).join(f"- **class {e.get('qclass','?')}** — {e['desc']}  ·  `{e['evidence']}`" for e in q) if q else "_None recorded._"}

---

## WHAT THIS RUN SHOWED

*Facts restated, not graded. No conclusion is drawn here — that is the point.*

{learned(routing, dev, problems, events)}

---

## HUMAN JUDGEMENT

*Yours alone. Never scored, never aggregated. The harness deliberately does not
attempt these — a generated answer here would be fabricated evidence.*

| Still requires you | Why it cannot be automated |
|---|---|
| The baseline | It only exists if you wrote it before seeing the output |
| Better than the baseline? | A comparison of two directions, not two strings |
| Did Ariadne add value? | Requires knowing what you would otherwise have shipped |
| Did anything feel like friction? | Only you were in the room |

### Baseline, captured before the run

{baseline if filled(baseline) else "_**Missing.** Without a baseline captured beforehand there is no control, and this run cannot show what Ariadne changed._"}

### Baseline vs Ariadne

{comp if filled(comp) else "_Not filled in._"}

Three questions only you can answer:

1. **Was the direction meaningfully different from your baseline?**
2. **Was the difference desirable** — or merely different?
3. **Did Ariadne prevent a default solution you would otherwise have shipped?**

> One instance of *"it made me reject X before I built it, and the replacement was
> better"* outweighs every count above.

---

## UNPROVEN

*Test A cannot reach these. Recording them stops a passing run from implying more
than it showed.*

| Not tested | Needs |
|---|---|
| Handoff sufficiency | Test B — a real `HANDOFF.md` consumed by a fresh session |
| Implementation fidelity to the thesis | Cursor, a multi-file build |
| Independent review | A separate session with no build context |
| Browser QA catching a real defect | A built artifact |
| Accessibility · performance · deployment | A built artifact |
| Provider switching | A second provider |
| Long-session behaviour, drift | Hours of real work |
| **Design quality** | **An independent reviewer. Never self-assessed.** |

---

## Recommendation

**Did this run produce enough evidence to change Ariadne?**

`<NO — FREEZE>` or `<YES — smallest change: …>`

> One occurrence is rarely enough. The loop in `templates/RETROSPECTIVE.md` requires a
> lesson to recur, or to have cost something nameable in hours. **After a first run,
> "freeze" is the expected answer** — and a run that changes nothing is still a run
> that told you something.
"""
    return out


def main():
    args = sys.argv[1:]
    run_dir = args[args.index("--run") + 1] if "--run" in args else latest_run()
    run_file = os.path.join(run_dir, "run.md") if os.path.isdir(run_dir) else run_dir
    if not os.path.exists(run_file):
        print(f"\nNo run record at {run_file}\n")
        return 1

    text = V.read(run_file)
    project = project_from_run(text)
    run_id = V.field(text, "Run ID") or os.path.basename(run_dir)

    print()
    print(BAR)
    print(f"ARIADNE  --  TEST A COLLECTION  ({run_id})")
    print(BAR)
    print()

    problems, events = V.check_run_file(text, run_file)
    observations = {}
    if project and os.path.isdir(project):
        p2, observations = V.check_project(project, V.field(text, "Mode"), None)
        problems += p2
    elif project:
        problems.append(f"project directory not found: {project}")
    problems += V.check_mode_drift()

    metrics = V.compute_metrics(events, observations)

    # Everything derivable from the raw reply is derived, so the human is left
    # only with what genuinely cannot be read off a file.
    tpath = os.path.join(run_dir, "evidence", "transcript.md")
    transcript = os.path.relpath(tpath, ROOT) if os.path.exists(tpath) else None
    routing = extract_routing(V.read(tpath)) if transcript else {}
    dev, ok = derive_deviations(routing, observations.get('documents_present'))

    result_path = os.path.join(run_dir, "RESULT.md")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(build_result(run_id, run_file, project, problems, events, observations,
                             metrics, routing, dev, ok, transcript))

    if not transcript:
        print("  ROUTING: not extracted -- no evidence/transcript.md.")
        print("           Paste the Codex reply there and re-run. Routing is the")
        print("           primary measurement of Test A.")
    else:
        print(f"  ROUTING: extracted from {transcript}")
        print(f"           confidence={routing.get('CONFIDENCE', '?')}  "
              f"object={routing.get('OBJECT', '?')[:32]}")
        for o in ok:
            print(f"    held      {o}")
        for d in dev:
            print(f"    DEVIATION {d}")
    print()

    for k, v in metrics.items():
        print(f"  {k}: {v}")

    # Name them. A count alone is not actionable -- the point of this metric is
    # to notice ceremony, which means knowing WHICH document appeared.
    extra = observations.get("conditional_documents_created", [])
    if extra:
        print("")
        print(f"  Conditional documents created: {extra}")
        print("  Each should have been triggered by a stated rule, not by habit.")
    print()
    if problems:
        print(f"  {len(problems)} structural problem(s):")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  Structure: OK")
    print()

    print(BAR)
    print("BENCHMARK")
    print(BAR)
    V.benchmark()
    print()

    print(BAR)
    print("BRING THESE BACK FOR ANALYSIS")
    print(BAR)
    print(f"  {os.path.relpath(result_path, ROOT)}")
    print(f"  {os.path.relpath(run_file, ROOT)}")
    print(f"  {os.path.relpath(os.path.join(run_dir, 'evidence'), ROOT)}/")
    if project:
        print(f"  {project}   (the project itself)")
    print()
    print("  RESULT.md separates PROVEN / OBSERVED / HUMAN JUDGEMENT / UNPROVEN.")
    print("  There is no overall score, deliberately -- a score would let a")
    print("  good-looking run stand in for a good project.")
    print()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
