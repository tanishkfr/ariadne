#!/usr/bin/env python3
"""
Builder OS consistency check.

Deterministic checks that caught real bugs during construction:
  1. Broken internal links
  2. Required files present (incl. one entry point per stage)
  3. Canonical rule IDs defined, no dangling references
  4. Router suite structure: categories, rules, modes, run history
  5. Stage chain: every chained prompt emits NEXT inside its fenced block
  6. AGENTS template: state fields present, no canonical policy duplicated
  7. Duplicated sentences (source-of-truth violations)

Usage:  python scripts/check.py [--verbose]
Exit:   0 clean, 1 problems found.

Everything here is deterministic. Anything requiring judgement is deliberately
absent -- see WORKFLOW.md for what stays human.
"""

import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERBOSE = "--verbose" in sys.argv

REQUIRED = [
    "README.md", "ROUTER.md", "WORKFLOW.md", "DESIGN-TASTE.md",
    "QA-POLICY.md", "EVALUATION-RUBRICS.md", "LIBRARY-POLICY.md",
    "CHANGELOG.md",
    "templates/PROJECT.md", "templates/DESIGN.md",
    "templates/HANDOFF.md", "templates/QA.md",
    # one entry point per active stage -- the v0.3 gap this closes
    "prompts/project-start.md", "prompts/design-direction.md",
    "prompts/build-kickoff.md", "prompts/project-review.md",
    "prompts/retrospective.md",
    "tests/router-cases.md",
    "adapters/codex.md", "adapters/cursor.md", "adapters/claude-code.md",
]

# Sentences allowed to repeat: gate names and block headers that must stay
# verbatim across files to remain greppable.
ALLOW_REPEAT = re.compile(
    r"^(g[1-5]|build finding|dependency request|routing block|ship request)",
    re.I,
)

# Files that legitimately restate rules because they LEAVE this repository:
#   prompts/*        pasted into a tool that cannot follow a link
#   templates/AGENTS.md  copied to a project root where Builder OS is absent
# Everything else must have one home. Do not add to this list to silence a
# real duplication -- fix the duplication instead.
#   validation/runs/*    every run record is a filled-in COPY of the run
#                        template -- that is what a run record is
DUPE_EXEMPT = ("prompts/", "templates/AGENTS.md", "validation/runs/")


def md_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for name in sorted(filenames):
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def check_links():
    """Every relative markdown link must resolve to a file on disk."""
    broken, count = [], 0
    for path in md_files():
        text = open(path, encoding="utf-8").read()
        for match in re.finditer(r"\]\(([^)]+)\)", text):
            link = match.group(1)
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            count += 1
            target = os.path.normpath(
                os.path.join(os.path.dirname(path), link.split("#")[0])
            )
            if not os.path.exists(target):
                broken.append((rel(path), link))
    return count, broken


def check_duplicates(min_words=9):
    """
    Sentences repeated verbatim across files mean a rule has two homes.
    When a rule changes, one copy gets updated and the other silently rots.
    """
    seen = collections.defaultdict(set)
    for path in md_files():
        if rel(path).startswith(DUPE_EXEMPT):
            continue
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"```.*?```", " ", text, flags=re.S)      # skip code blocks
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)    # unwrap links
        text = re.sub(r"[*`>#|_-]", " ", text)                  # strip markup
        for raw in re.split(r"(?<=[.!?])\s+|\n", text):
            sentence = " ".join(raw.split())
            if len(sentence.split()) >= min_words and not ALLOW_REPEAT.match(sentence):
                seen[sentence].add(rel(path))
    return {s: f for s, f in seen.items() if len(f) > 1}


def check_required():
    return [f for f in REQUIRED if not os.path.exists(os.path.join(ROOT, f))]


# Canonical routing rules. Defined once in ROUTER.md's rule index; referenced by
# ID elsewhere so a rule has one home instead of four paraphrases.
RULE_IDS = [
    "R-ACT-1", "R-REF-1", "R-REF-2", "R-XFM-1", "R-DEST-1",
    "R-INT-1", "R-PAT-1", "R-CONF-1", "R-ASK-1",
]
RULE_SOURCE = "ROUTER.md"


def check_rule_ids():
    """
    Two failure modes, both cheap to detect:
      - a rule ID is referenced somewhere but never defined (dangling reference)
      - a canonical rule ID vanished from ROUTER.md (silent deletion)
    This deliberately does NOT check that the rule still says what the
    referencing file assumes. No semantic engine -- only a human read catches that.
    """
    src = os.path.join(ROOT, RULE_SOURCE)
    defined = set()
    if os.path.exists(src):
        text = open(src, encoding="utf-8").read()
        for rid in RULE_IDS:
            # "defined" means it appears in the rule index table
            if re.search(r"\*\*" + re.escape(rid) + r"\*\*\s*\|", text):
                defined.add(rid)

    missing = [r for r in RULE_IDS if r not in defined]

    referenced = collections.defaultdict(set)
    for path in md_files():
        text = open(path, encoding="utf-8").read()
        for rid in set(re.findall(r"\bR-[A-Z]{2,8}-\d+\b", text)):
            referenced[rid].add(rel(path))

    dangling = {r: f for r, f in referenced.items() if r not in RULE_IDS}
    return missing, dangling


# Router suite guard. Structure only -- whether a case still PASSES needs a
# reasoning agent, not a script. This catches the cheap failures: the suite
# vanishing, a category being dropped, or a case citing a rule/mode that no
# longer exists.
ROUTER_SUITE = "tests/router-cases.md"
REQUIRED_CATEGORIES = [
    "Core cases", "CREATE with a reference", "ANALYZE",
    "Portfolio wording", "TRANSFORM", "RESTART",
    "Anti-generic intent", "Constraint preservation",
]
MODES = [
    "client-or-portfolio", "product-app", "game-experiment",
    "content-system", "audit-review",
]


def check_router_suite():
    problems = []
    path = os.path.join(ROOT, ROUTER_SUITE)
    if not os.path.exists(path):
        return [f"{ROUTER_SUITE} is missing -- the router cannot be safely changed without it"]

    text = open(path, encoding="utf-8").read()

    # Must appear in a real "## Category N -- Name" heading. A plain substring
    # search over the whole file was vacuous: category words also occur in the
    # Expect column, so a renamed heading still passed. Caught by negative test.
    heading_re = r"(?m)^##\s+Category\s+\d+[^\r\n]*"
    headings = " | ".join(re.findall(heading_re, text))
    for cat in REQUIRED_CATEGORIES:
        if cat not in headings:
            problems.append(f"missing required category heading: {cat}")

    # every rule ID cited by a test must be canonical
    for rid in sorted(set(re.findall(r"\bR-[A-Z]{2,8}-\d+\b", text))):
        if rid not in RULE_IDS:
            problems.append(f"cites non-canonical rule {rid}")

    # every mode named must still exist as a mode file
    for mode in sorted(set(re.findall(r"\b(?:" + "|".join(MODES) + r")\b", text))):
        if not os.path.exists(os.path.join(ROOT, "modes", mode + ".md")):
            problems.append(f"references deleted mode: {mode}")

    # guard against a mode being removed from the repo but left in the suite
    for f in os.listdir(os.path.join(ROOT, "modes")):
        if f.endswith(".md") and f[:-3] not in MODES:
            problems.append(f"mode {f[:-3]} exists but is not in the suite's MODES list")

    if "## Result log" not in text:
        problems.append("no Result log section -- regressions are invisible without run history")

    return problems


# Stage chain guard. B1 (v0.3.2) was: the NEXT instruction sat in prose OUTSIDE
# the fenced block, so the agent receiving the pasted prompt never saw it and
# the workflow chain silently broke at S3 and S4. Prose around a fence is
# documentation for the human; only the fence reaches the agent.
CHAINED_PROMPTS = [
    "prompts/project-start.md",
    "prompts/design-direction.md",
    "prompts/build-kickoff.md",
    "prompts/project-review.md",
]


def check_stage_chain():
    problems = []
    for rel_path in CHAINED_PROMPTS:
        full = os.path.join(ROOT, rel_path)
        if not os.path.exists(full):
            problems.append(f"{rel_path} missing")
            continue
        text = open(full, encoding="utf-8").read()
        fenced = " ".join(re.findall(r"```(.*?)```", text, re.S))
        if "NEXT:" not in fenced:
            where = "in prose only" if "NEXT" in text else "absent"
            problems.append(
                f"{rel_path}: NEXT instruction {where} -- must be INSIDE the "
                f"fenced block or the agent never receives it"
            )
    return problems


# Project AGENTS.md template guard. Structure only.
#
# AGENTS.md is the runtime state file that ships into a project repo. It is
# canonical for exactly two things -- Current state and Do not change -- and a
# mirror for everything else. Two failure modes are cheap to detect:
#   1. a required state field goes missing, so a fresh session cannot tell
#      where the project is
#   2. a canonical policy block gets pasted in wholesale, creating a second
#      policy system that will silently drift from the real one
# Whether a reminder has drifted in MEANING is not checkable here. Only reading is.
AGENTS_TEMPLATE = "templates/AGENTS.md"
AGENTS_REQUIRED_FIELDS = [
    "**Stage**", "**Last gate passed**", "**Next stage**",
    "**Next prompt**", "**Updated**",
]
VALID_STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
VALID_GATES = ["G1", "G2", "G3", "G4", "G5"]

# Sentences whose canonical home is a Builder OS policy file. If one appears
# verbatim in the AGENTS template, the template has started owning a rule.
CANON_MARKERS = [
    ("A gate is a full stop", "WORKFLOW.md"),
    ("Approval covers one action, once", "WORKFLOW.md"),
    ("The evidence rule", "QA-POLICY.md"),
    ("Blocking by default:", "QA-POLICY.md"),
    ("The escalation ladder", "QA-POLICY.md"),
    ("intentionality test", "ROUTER.md"),
    ("Three minimum", "ROUTER.md"),
    ("statistical centre", "DESIGN-TASTE.md"),
]


def check_agents_template():
    problems = []
    full = os.path.join(ROOT, AGENTS_TEMPLATE)
    if not os.path.exists(full):
        return [f"{AGENTS_TEMPLATE} is missing -- projects have no runtime state file"]

    text = open(full, encoding="utf-8").read()

    if "## Current state" not in text:
        problems.append("no '## Current state' section -- a fresh session cannot locate the project")
    for field in AGENTS_REQUIRED_FIELDS:
        if field not in text:
            problems.append(f"Current state missing required field: {field}")

    # stage / gate identifiers must be well formed where they are enumerated
    for stage in re.findall(r"\bS\d+\b", text):
        if stage not in VALID_STAGES:
            problems.append(f"malformed stage identifier: {stage}")
    for gate in re.findall(r"\bG\d+\b", text):
        if gate not in VALID_GATES:
            problems.append(f"malformed gate identifier: {gate}")

    # the template must say it is not canonical, or the precedence inverts
    if "never becomes the owner" not in text and "not canonical" not in text:
        problems.append("template does not state it is non-canonical -- risks inverting precedence")

    for marker, owner in CANON_MARKERS:
        if marker in text:
            problems.append(f"contains canonical block from {owner}: \"{marker}\"")

    return problems


def main():
    failed = False

    total, broken = check_links()
    if broken:
        failed = True
        print(f"FAIL  links: {len(broken)} broken of {total}")
        for path, link in broken:
            print(f"        {path} -> {link}")
    else:
        print(f"ok    links: {total} checked, 0 broken")

    missing = check_required()
    if missing:
        failed = True
        print(f"FAIL  required files: {len(missing)} missing")
        for f in missing:
            print(f"        {f}")
    else:
        print(f"ok    required files: {len(REQUIRED)} present")

    missing_rules, dangling = check_rule_ids()
    if missing_rules or dangling:
        failed = True
        if missing_rules:
            print(f"FAIL  rule IDs: {len(missing_rules)} not defined in {RULE_SOURCE}")
            for r in missing_rules:
                print(f"        {r}")
        for rid, files in sorted(dangling.items()):
            print(f"FAIL  rule IDs: {rid} referenced but not canonical")
            for f in sorted(files):
                print(f"        {f}")
    else:
        print(f"ok    rule IDs: {len(RULE_IDS)} defined, no dangling references")

    agents_problems = check_agents_template()
    if agents_problems:
        failed = True
        print(f"FAIL  AGENTS template: {len(agents_problems)} problem(s)")
        for a in agents_problems:
            print(f"        {a}")
    else:
        print(f"ok    AGENTS template: {len(AGENTS_REQUIRED_FIELDS)} state fields, no canonical policy copied")

    chain_problems = check_stage_chain()
    if chain_problems:
        failed = True
        print(f"FAIL  stage chain: {len(chain_problems)} broken transition(s)")
        for c in chain_problems:
            print(f"        {c}")
    else:
        print(f"ok    stage chain: {len(CHAINED_PROMPTS)} prompts emit NEXT inside the fence")

    suite_problems = check_router_suite()
    if suite_problems:
        failed = True
        print(f"FAIL  router suite: {len(suite_problems)} problem(s)")
        for p in suite_problems:
            print(f"        {p}")
    else:
        print(f"ok    router suite: {len(REQUIRED_CATEGORIES)} categories, rules and modes valid")

    dupes = check_duplicates()
    if dupes:
        failed = True
        print(f"FAIL  duplicated sentences: {len(dupes)}")
        shown = sorted(dupes.items(), key=lambda kv: -len(kv[1]))
        for sentence, files in (shown if VERBOSE else shown[:10]):
            print(f"        [{len(files)}] {sorted(files)}")
            print(f'          "{sentence[:100]}"')
        if not VERBOSE and len(dupes) > 10:
            print(f"        ... {len(dupes) - 10} more (--verbose)")
    else:
        print("ok    duplicated sentences: 0")

    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
