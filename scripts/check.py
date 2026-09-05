#!/usr/bin/env python3
"""
Ariadne consistency check.

Deterministic checks that caught real bugs during construction:
  1. Broken internal links
  2. Required files present (incl. one entry point per stage)
  3. Canonical rule IDs defined, no dangling references
  4. Router suite structure: categories, rules, modes, run history
  5. Stage chain: every chained prompt emits NEXT inside its fenced block
  6. AGENTS template: state fields present, no canonical policy duplicated
  7. S1 AGENTS transport mirror: exact copy of the canonical template contract
  8. Standalone stage delivery: inputs, missing paths, transitions, adapters
  9. Duplicated sentences (source-of-truth violations)

Usage:  python scripts/check.py [--verbose | --self-test]
Exit:   0 clean, 1 problems found.

Everything here is deterministic. Anything requiring judgement is deliberately
absent -- see WORKFLOW.md for what stays human.
"""

import os
import re
import sys
import collections
import copy
import importlib.util
import json
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERBOSE = "--verbose" in sys.argv
SELF_TEST = "--self-test" in sys.argv

REQUIRED = [
    "README.md", "ROUTER.md", "WORKFLOW.md", "DESIGN-TASTE.md",
    "QA-POLICY.md", "EVALUATION-RUBRICS.md", "LIBRARY-POLICY.md",
    "PRIVACY-POLICY.md", "references/capabilities.json",
    "CHANGELOG.md", "QUICKSTART.md", "INSTALL.md", "UPDATE.md",
    "TROUBLESHOOTING.md", "RELEASING.md", "V1.4-READINESS.md", "V1.5-READINESS.md",
    "V1.5.1-READINESS.md", "V1.5.2-READINESS.md", "V1.5.3-READINESS.md",
    "V1.6-READINESS.md",
    "CODEX-ENVIRONMENT.md", "RELEASE-NOTES.md",
    "VERSION", "LICENSE", "pyproject.toml", "build_backend/ariadne_backend.py",
    "src/ariadne/__init__.py", "src/ariadne/__main__.py", "src/ariadne/cli.py",
    "templates/PROJECT.md", "templates/DESIGN.md",
    "templates/HANDOFF.md", "templates/QA.md", "templates/RETURN-HANDOFF.md",
    "templates/SOCIAL-STRATEGY.md",
    # one entry point per active stage -- the v0.3 gap this closes
    "prompts/project-start.md", "prompts/research.md", "prompts/design-direction.md",
    "prompts/build-kickoff.md", "prompts/project-review.md",
    "prompts/retrospective.md",
    "tests/router-cases.md",
    "adapters/codex.md", "adapters/cursor.md", "adapters/claude-code.md",
    "adapters/reasoner-contract.md", "adapters/reasoners.json",
    "adapters/claude-reasoner.md", "adapters/claude-reasoner-skill/SKILL.md",
    "adapters/codex-baseline.md",
    "scripts/prepare-stage.py", "scripts/ariadne.py", "scripts/creative-intelligence.py",
    "scripts/creative-operations.py", "scripts/reasoners.py",
    "scripts/install-claude-reasoner-skill.py",
    "scripts/test-reasoner-rollback.py",
    "scripts/test-real-projects.py", "validation/fixtures/v1.5-real-projects.json",
    "validation/fixtures/v1.5.1-reasoner-flows.json",
    "scripts/test-social-intelligence.py", "validation/fixtures/v1.5.2-social-flows.json",
    "scripts/install-ariadne-skill.py",
    "scripts/build-release.py", "scripts/test-distribution.py",
    "scripts/test-wheel-install.py",
    ".agents/skills/ariadne/SKILL.md",
    ".agents/skills/ariadne/agents/openai.yaml",
    ".agents/skills/ariadne/references/creative-intelligence.md",
    ".agents/skills/ariadne/references/creative-operations.md",
    "skills/visual-qa.md", "skills/creative-review.md", "skills/social-strategy.md",
]

# Sentences allowed to repeat: gate names and block headers that must stay
# verbatim across files to remain greppable.
ALLOW_REPEAT = re.compile(
    r"^(g[1-5]|build finding|dependency request|routing block|ship request)",
    re.I,
)

# Files that legitimately restate rules because they LEAVE this repository:
#   prompts/*        pasted into a tool that cannot follow a link
#   templates/AGENTS.md  copied to a project root where Ariadne is absent
# Everything else must have one home. Do not add to this list to silence a
# real duplication -- fix the duplication instead.
DUPE_EXEMPT = ("prompts/", "templates/AGENTS.md")

# This script verifies ARIADNE. validation/runs/ holds the OUTPUT of
# experiments run with it -- generated artifacts, not canonical documentation.
#
# They are excluded here for a structural reason, not for convenience: while
# they were included, a stale record left by an OLD run failed check.py, and
# setup-test-a.py refuses to start when check.py fails. A finished experiment
# could therefore permanently block every future experiment, and the more runs
# you did the likelier that became.
#
# Their links are still checked -- by validate.py, where a broken link is a
# finding about THAT RUN rather than a repository-wide failure. check.py owns
# the repository; validate.py owns a run. Do not merge the two.
GENERATED = ("validation/runs/",)
EXCLUDED_SCAN_DIRS = {
    ".git", ".next", "__pycache__", "build", "dist", "node_modules",
}
EPHEMERAL_SELF_TEST = (
    re.compile(
        r"^validation/(?:ariadne|creative-intelligence|creative-operations|distribution|packet|real-projects|release|skill-install|social|wheel)-self-test-[0-9a-f]{32}/"
    ),
    re.compile(r"^validation/validate-self-test-[a-z0-9-]+/"),
)

SKILL_FILES = [
    "skills/intake.md",
    "skills/reference-analysis.md",
    "skills/component-research.md",
    "skills/design-direction.md",
    "skills/visual-qa.md",
    "skills/creative-review.md",
    "skills/social-strategy.md",
]

DEPENDENCY_AUTHORITY_FILES = (
    "WORKFLOW.md", "LIBRARY-POLICY.md", "prompts/build-kickoff.md",
    "references/capabilities.json", "scripts/creative-intelligence.py",
    "skills/component-research.md",
)
EVIDENCE_LADDER_FILES = (
    "RESEARCH-POLICY.md", "templates/RESEARCH.md", "prompts/research.md",
    "scripts/creative-intelligence.py",
    ".agents/skills/ariadne/references/creative-intelligence.md",
)
AGENT_SECURITY_FILES = (
    "PRIVACY-POLICY.md", "prompts/research.md", "prompts/design-direction.md",
    "skills/component-research.md", "skills/reference-analysis.md",
)


def generated_markdown(relative_path):
    return relative_path.startswith(GENERATED) or any(
        pattern.match(relative_path) for pattern in EPHEMERAL_SELF_TEST
    )


def excluded_scan_path(relative_path):
    """Return true for reproducible or tool-owned trees, never source trees."""
    return any(part in EXCLUDED_SCAN_DIRS for part in relative_path.split("/"))


def check_skill_contract_texts(texts=None):
    """Every executable skill declares its boundary and completion condition."""
    values = dict(texts or {})
    problems = []
    for relative in SKILL_FILES:
        text = values.get(relative)
        if text is None:
            text = open(os.path.join(ROOT, relative), encoding="utf-8").read()
        expected_name = os.path.splitext(os.path.basename(relative))[0]
        if not re.search(rf"(?m)^# SKILL:\s*{re.escape(expected_name)}\s*$", text):
            problems.append(f"skill name/path mismatch: {relative}")
        for field in ("Trigger", "Owner", "Inputs", "Output"):
            if len(re.findall(rf"(?m)^\*\*{field}\*\*\s+—\s+\S", text)) != 1:
                problems.append(f"skill contract missing or duplicates {field}: {relative}")
        if not re.search(r"(?m)^## (?:Done when|Stop conditions)\s*$", text):
            problems.append(f"skill contract has no completion or stop section: {relative}")
    return problems


def check_dependency_authority_texts(texts=None):
    """Discovery and defaults must never silently grant the human G2 gate."""
    values = dict(texts or {})
    for relative in DEPENDENCY_AUTHORITY_FILES:
        if relative not in values:
            values[relative] = open(
                os.path.join(ROOT, relative), encoding="utf-8"
            ).read()
    library = values["LIBRARY-POLICY.md"]
    problems = []
    required = (
        "Every exact dependency set still",
        "requires human G2 approval before the first install command",
        "Discovery never grants",
    )
    if any(token not in library for token in required):
        problems.append("library policy does not preserve exact human G2 authority")
    if re.search(r"(?im)^Installable without asking|\|\s*\*\*Approved\*\*.*\|\s*None needed\s*\|", library):
        problems.append("library policy still contains a dependency self-approval path")
    if "Any new package" not in values["WORKFLOW.md"]:
        problems.append("workflow no longer sends every new package to G2")
    if "NO NEW DEPENDENCY without asking me (G2)" not in values["prompts/build-kickoff.md"]:
        problems.append("build prompt no longer stops before an unapproved dependency")
    try:
        registry = json.loads(values["references/capabilities.json"])
    except json.JSONDecodeError:
        registry = {}
        problems.append("capability registry is malformed JSON")
    if registry.get("canonical_owner") != "LIBRARY-POLICY.md":
        problems.append("capability registry no longer points to the canonical library policy")
    if "never installation authority" not in registry.get("purpose", ""):
        problems.append("capability registry can be mistaken for installation authority")
    runtime = values["scripts/creative-intelligence.py"]
    if '"install_authority": "none — human G2 required"' not in runtime:
        problems.append("capability planning no longer preserves human G2")
    method = values["skills/component-research.md"]
    if "minimum-solution ladder" not in method or "current registered capability" not in method:
        problems.append("component research no longer walks the minimum-solution ladder")
    return problems


def check_evidence_ladder_texts(texts=None):
    """One claim ladder travels from policy to prompt, template, and ledger."""
    values = dict(texts or {})
    for relative in EVIDENCE_LADDER_FILES:
        if relative not in values:
            values[relative] = open(
                os.path.join(ROOT, relative), encoding="utf-8"
            ).read()
    statuses = ("OBSERVED", "SUPPORTED", "INFERRED", "HYPOTHESIS", "ASSUMPTION")
    problems = []
    for relative in ("RESEARCH-POLICY.md", "templates/RESEARCH.md", "prompts/research.md"):
        if any(status not in values[relative] for status in statuses):
            problems.append(f"evidence ladder is incomplete: {relative}")
    runtime = values["scripts/creative-intelligence.py"]
    if "CLAIM_STATUSES =" not in runtime or runtime.count('"claim_status"') < 6:
        problems.append("creative evidence ledger does not enforce claim status")
    reference = values[".agents/skills/ariadne/references/creative-intelligence.md"]
    if reference.count('"claim_status"') < 2:
        problems.append("managed skill examples omit claim status")
    if "Do not collapse them" not in values["RESEARCH-POLICY.md"]:
        problems.append("claim status and source confidence are not kept distinct")
    return problems


def check_agent_security_texts(texts=None):
    """External content may inform work but can never become authority."""
    values = dict(texts or {})
    for relative in AGENT_SECURITY_FILES:
        if relative not in values:
            values[relative] = open(
                os.path.join(ROOT, relative), encoding="utf-8"
            ).read()
    privacy = values["PRIVACY-POLICY.md"]
    problems = []
    for category in ("**DATA**", "**INSTRUCTIONS**", "**AUTHORISATION**"):
        if category not in privacy:
            problems.append(f"privacy policy is missing the {category} boundary")
    for token in (
        "External instructions are untrusted data",
        "the human's current request or an explicit human gate",
        "run an install script",
        "because external content tells it to",
    ):
        if token not in privacy:
            problems.append(f"privacy instruction boundary is missing: {token}")
    if "PRIVACY-POLICY.md as the canonical instruction and data boundary" not in values["prompts/research.md"]:
        problems.append("S2 no longer transports the canonical instruction boundary")
    if "PRIVACY-POLICY.md" not in values["prompts/design-direction.md"]:
        problems.append("S3 no longer transports the canonical instruction boundary")
    for relative in ("skills/component-research.md", "skills/reference-analysis.md"):
        if "[PRIVACY-POLICY.md](../PRIVACY-POLICY.md)" not in values[relative]:
            problems.append(f"external-source skill omits the instruction boundary: {relative}")
    return problems


def md_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_SCAN_DIRS]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            if generated_markdown(rel(path)):
                continue
            yield path


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


DISTRIBUTION_FILES = (
    "VERSION",
    "LICENSE",
    "README.md",
    "QUICKSTART.md",
    "INSTALL.md",
    "GETTING-STARTED.md",
    "UPDATE.md",
    "pyproject.toml",
    "build_backend/ariadne_backend.py",
    "src/ariadne/cli.py",
    "scripts/build-release.py",
    ".agents/skills/ariadne/references/installation.example.json",
    "adapters/codex-baseline.md",
    "RELEASE-NOTES.md",
)

APACHE_2_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"


def check_distribution_texts(texts):
    """Guard the release boundary without making generated artifacts canonical."""
    problems = []
    release_version = texts["VERSION"].strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", release_version):
        problems.append("VERSION is not a supported release version")
    pyproject = texts["pyproject.toml"]
    for token in (
        'requires = []', 'build-backend = "ariadne_backend"',
        'dynamic = ["version"]', 'dependencies = []', 'requires-python = ">=3.10"',
        'ariadne = "ariadne.cli:main"', 'license = "Apache-2.0"',
        'License :: OSI Approved :: Apache Software License',
        'Changelog = "https://github.com/tanishkfr/ariadne/blob/master/CHANGELOG.md"',
    ):
        if token not in pyproject:
            problems.append(f"pyproject.toml is missing the release contract: {token}")
    if re.search(r"(?m)^version\s*=", pyproject):
        problems.append("pyproject.toml duplicates the canonical VERSION value")
    licence_sha = hashlib.sha256(texts["LICENSE"].encode("utf-8")).hexdigest()
    if licence_sha != APACHE_2_LICENSE_SHA256:
        problems.append("LICENSE is not the approved canonical Apache-2.0 text")
    backend = texts["build_backend/ariadne_backend.py"]
    for token in (
        "ariadne/seed-runtime.zip", "scripts\" / \"build-release.py",
        "License-Expression: Apache-2.0", "licenses/LICENSE",
        "Requires-Python: >=3.10",
        "Project-URL: Changelog, https://github.com/tanishkfr/ariadne/blob/master/CHANGELOG.md",
    ):
        if token not in backend:
            problems.append(f"wheel backend is missing: {token}")
    cli = texts["src/ariadne/cli.py"]
    for token in (
        "https://github.com/tanishkfr/ariadne/releases/latest/download/",
        "def install_seed_runtime(", 'sub.add_parser("update"',
        'sub.add_parser("rollback"', 'sub.add_parser("doctor"',
        'sub.add_parser("uninstall"', 'sub.add_parser("enable-claude"',
        'sub.add_parser("disable-claude"', 'sub.add_parser("codex-baseline"',
        'preferred = home / ".agents" / "skills"', "def install_codex_baseline(",
        "def remove_codex_baseline(", "def refresh_codex_baseline_if_managed(",
        "MIN_PYTHON = (3, 10)", '"User-Agent": "Ariadne-installer"',
    ):
        if token not in cli:
            problems.append(f"launcher is missing: {token}")
    release = texts["scripts/build-release.py"]
    for token in (
        "RUNTIME_TOP_LEVEL", "RUNTIME_TREES", "RUNTIME_SCRIPTS",
        '"VERSION", "LICENSE"',
        "RELEASE-MANIFEST.json", "SHA256SUMS.txt", "release_notes",
        "publication_state", "PACKAGING CANDIDATE",
        '"requires_python": ">=3.10"',
    ):
        if token not in release:
            problems.append(f"release builder is missing: {token}")
    if re.search(
        r"(?s)RUNTIME_(?:TOP_LEVEL|TREES)\s*=\s*\[[^\]]*"
        r"(?:validation|operations|tests)",
        release,
    ):
        problems.append("release allowlist includes maintainer-only trees")
    baseline = texts["adapters/codex-baseline.md"]
    for token in (
        "Inspect existing instructions", "smallest reversible change",
        "Avoid destructive actions", "Distinguish verified facts",
    ):
        if token not in baseline:
            problems.append(f"Codex baseline is missing a general working default: {token}")
    if re.search(r"(?i)\b(?:G[1-5]|S[0-6]|Ariadne|provider routing|social strategy)\b", baseline):
        problems.append("Codex baseline contains Ariadne workflow or project policy")
    install_url = (
        "https://github.com/tanishkfr/ariadne/releases/download/"
        f"v{release_version}/ariadne-{release_version}-py3-none-any.whl"
    )
    for path in ("README.md", "QUICKSTART.md", "INSTALL.md", "GETTING-STARTED.md"):
        if install_url not in texts[path]:
            problems.append(f"{path} does not install the immutable current release wheel")
        if "archive/refs/heads/master.zip" in texts[path]:
            problems.append(f"{path} installs from a moving source branch")
    for token in (
        "python -m ariadne --version",
        "python -m ariadne update",
        "python -m ariadne rollback",
        "python -m ariadne uninstall",
        "python -m pip uninstall ariadne",
        "python -m pip show ariadne",
        "Projects, project documents, evidence, source files",
    ):
        if token not in texts["README.md"]:
            problems.append(f"README.md omits installed lifecycle guidance: {token}")
    release_notes = texts["RELEASE-NOTES.md"]
    if not re.search(rf"(?m)^# Ariadne {re.escape(release_version)}\s*$", release_notes):
        problems.append("release notes do not name the authoritative VERSION")
    for token in ("first-time-user", "comprehension", "macOS", "Linux", "Codex"):
        if token not in release_notes:
            problems.append(f"release notes omit an evidence boundary: {token}")
    try:
        example = json.loads(texts[".agents/skills/ariadne/references/installation.example.json"])
    except json.JSONDecodeError as exc:
        problems.append(f"installation example is malformed: {exc}")
    else:
        for key in ("schema_version", "ariadne_root", "install_home", "version"):
            if not example.get(key):
                problems.append(f"installation example is missing {key}")
    return problems


def check_distribution():
    texts = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in DISTRIBUTION_FILES
        if os.path.isfile(os.path.join(ROOT, path))
    }
    missing = sorted(set(DISTRIBUTION_FILES) - set(texts))
    return [f"distribution source is missing: {path}" for path in missing] + (
        check_distribution_texts(texts) if not missing else []
    )


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
    "prompts/research.md",
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
AGENTS_PROMPT = "prompts/project-start.md"
AGENTS_MIRROR_BEGIN = (
    "BEGIN AGENTS TEMPLATE TRANSPORT MIRROR "
    "(non-canonical; canonical owner: templates/AGENTS.md)"
)
AGENTS_MIRROR_END = "END AGENTS TEMPLATE TRANSPORT MIRROR"
AGENTS_REQUIRED_FIELDS = [
    "**Stage**", "**Last gate passed**", "**Next stage**",
    "**Next prompt**", "**Updated**",
]
VALID_STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
VALID_GATES = ["G1", "G2", "G3", "G4", "G5"]

# Sentences whose canonical home is an Ariadne policy file. If one appears
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


# Standalone delivery-contract guard. Each provider session receives only its
# project repository, pasted stage prompt, and explicitly delivered stage inputs.
# These checks protect that transport boundary without copying or interpreting
# the canonical policies themselves.
DELIVERY_CONTRACTS = [
    {
        "path": "prompts/project-start.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "skills/intake.md",
            "AGENTS template transport mirror", "IF MISSING",
            "NEXT: S3 Design direction.",
        ],
        "inputs": ["skills/intake.md", "AGENTS template transport mirror"],
        "retry": "NEXT: S1 Discovery resume.",
        "forbidden_missing": ["NEXT: S3 Design direction."],
    },
    {
        "path": "prompts/research.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "QUESTIONS", "RESEARCH-POLICY.md",
            "PRIVACY-POLICY.md", "templates/RESEARCH.md",
            ".ariadne/creative-evidence.json", "IF MISSING",
            "RESOURCE EVIDENCE", "compatibility", "licence", "alternatives",
            "NEXT: S3 Design direction.",
        ],
        "inputs": [
            "QUESTIONS", "RESEARCH-POLICY.md", "PRIVACY-POLICY.md",
            "templates/RESEARCH.md", ".ariadne/creative-evidence.json",
        ],
        "retry": "NEXT: S2 Research retry.",
        "forbidden_missing": ["NEXT: S3 Design direction."],
    },
    {
        "path": "prompts/design-direction.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "PROJECT.md", "DESIGN-TASTE.md",
            "PRIVACY-POLICY.md", "templates/DESIGN.md", "skills/design-direction.md",
            "skills/reference-analysis.md", "skills/component-research.md",
            "references/capabilities.json", "DESIGN-MOTION.md", "DESIGN-ASSETS.md",
            ".ariadne/creative-evidence.json", "IF MISSING", "NEXT: S4 Build.",
        ],
        "inputs": [
            "PROJECT.md", "DESIGN-TASTE.md", "PRIVACY-POLICY.md",
            "templates/DESIGN.md", "skills/design-direction.md",
            "skills/reference-analysis.md", "skills/component-research.md",
            "references/capabilities.json",
            "DESIGN-MOTION.md", "DESIGN-ASSETS.md", ".ariadne/creative-evidence.json",
        ],
        "retry": "NEXT: S3 Design direction retry.",
        "forbidden_missing": ["NEXT: S4 Build."],
    },
    {
        "path": "prompts/build-kickoff.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "PROJECT.md", "DESIGN.md", "AGENTS.md",
            "templates/HANDOFF.md", "IF MISSING", "NEXT: S4 Build.",
            "Return to Ariadne", "templates/RETURN-HANDOFF.md",
        ],
        "inputs": ["PROJECT.md", "DESIGN.md", "AGENTS.md", "templates/HANDOFF.md"],
        "retry": "NEXT: S4 Handoff retry.",
        "forbidden_missing": ["NEXT: S4 Build."],
    },
    {
        "path": "prompts/build-kickoff.md",
        "block": 1,
        "tokens": [
            "REQUIRED INPUTS", "HANDOFF.md", "DESIGN.md", "AGENTS.md",
            "QA-POLICY.md", "templates/QA.md", "IF MISSING",
            "templates/RETURN-HANDOFF.md", "BEGIN/END markers",
            ".ariadne/creative-operations.json", "skills/visual-qa.md",
            "feature-branch preview", "already connected",
            "NEXT: S5 Review.",
        ],
        "inputs": [
            "HANDOFF.md", "DESIGN.md", "AGENTS.md", "QA-POLICY.md",
            "templates/QA.md", "templates/RETURN-HANDOFF.md",
            ".ariadne/creative-operations.json", "skills/visual-qa.md",
        ],
        "retry": "NEXT: S4 Build retry.",
        "forbidden_missing": ["NEXT: S5 Review."],
    },
    {
        "path": "prompts/project-review.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "TARGET", "INTENT", "CRITERIA",
            "ACCEPTED PATTERNS", "EVALUATION-RUBRICS.md", "IF MISSING",
            "BEGIN QA JUDGEMENT", "END QA JUDGEMENT",
            "After I grant G3:", "NEXT: G4 Ship request.",
        ],
        "inputs": [
            "TARGET", "INTENT", "CRITERIA", "ACCEPTED PATTERNS",
            "EVALUATION-RUBRICS.md",
        ],
        "retry": "NEXT: S5 Review retry.",
        "forbidden_missing": ["NEXT: G4 Ship request."],
    },
    {
        "path": "prompts/retrospective.md",
        "block": 0,
        "tokens": [
            "REQUIRED INPUTS", "PROJECT.md", "QA.md", "AGENTS.md",
            "independent S5 QA judgement block", "templates/RETROSPECTIVE.md",
            "IF MISSING",
        ],
        "inputs": ["PROJECT.md", "QA.md", "AGENTS.md", "templates/RETROSPECTIVE.md"],
        "retry": "NEXT: S6 Retrospective retry.",
        "forbidden_missing": [],
    },
    {
        "path": "prompts/content-system.md",
        "block": 1,
        "tokens": [
            "REQUIRED INPUTS", "voice-profile.md", "anti-voice",
            "pillars list", "CONTENT-LEARNINGS.md", "RAW MATERIAL",
            "PLATFORM", "PILLAR", "IF MISSING",
        ],
        "inputs": [
            "voice-profile.md", "anti-voice", "pillars list",
            "CONTENT-LEARNINGS.md", "RAW MATERIAL", "PLATFORM", "PILLAR",
        ],
        "retry": "NEXT: Content drafting retry.",
        "forbidden_missing": ["G5: PUBLISH REQUEST"],
    },
    {
        "path": "prompts/content-system.md",
        "block": 2,
        "tokens": [
            "REQUIRED INPUTS", "current CONTENT-LEARNINGS.md",
            "posts, numbers, and qualitative reply evidence", "IF MISSING",
            "READ the current CONTENT-LEARNINGS.md",
        ],
        "inputs": [
            "current CONTENT-LEARNINGS.md",
            "posts, numbers, and qualitative reply evidence",
        ],
        "retry": "NEXT: Weekly content review retry.",
        "forbidden_missing": [],
    },
]

ADAPTER_DELIVERY = {
    "adapters/codex.md": {
        "begin": "**What to attach per stage:**",
        "end": "If a required input is unavailable",
        "tokens": [
            "skills/intake.md", "RESEARCH-POLICY.md", "PRIVACY-POLICY.md",
            "templates/RESEARCH.md", "DESIGN-TASTE.md", "templates/DESIGN.md",
            "skills/design-direction.md", "skills/reference-analysis.md",
            "skills/component-research.md", "references/capabilities.json", "DESIGN-MOTION.md",
            "DESIGN-ASSETS.md", ".ariadne/creative-evidence.json", "templates/HANDOFF.md",
            ".ariadne/creative-operations.json", "skills/visual-qa.md",
            "EVALUATION-RUBRICS.md", "completed `QA.md`",
            "templates/RETROSPECTIVE.md",
        ],
    },
    "adapters/cursor.md": {
        "begin": "### Fresh-session input matrix",
        "end": "If a required S4B input is unavailable",
        "tokens": [
            "HANDOFF.md", "DESIGN.md", "AGENTS.md", "QA-POLICY.md",
            "templates/QA.md", "templates/RETURN-HANDOFF.md",
            ".ariadne/creative-operations.json", "skills/visual-qa.md",
            "explicit human G3 approval",
        ],
    },
}


def fenced_blocks(text):
    return re.findall(r"(?ms)^```[^\r\n]*\r?\n(.*?)^```\s*$", text)


def missing_contract(block):
    match = re.search(r"(?ms)^IF MISSING\s*$\r?\n(.*?)^END IF MISSING\s*$", block)
    return match.group(1) if match else None


def required_inputs_contract(block):
    match = re.search(r"(?ms)^REQUIRED INPUTS\s*$\r?\n(.*?)^IF MISSING\s*$", block)
    return match.group(1) if match else None


def check_delivery_contract_texts(texts):
    problems = []
    for spec in DELIVERY_CONTRACTS:
        path = spec["path"]
        text = texts.get(path)
        if text is None:
            problems.append(f"{path} missing from delivery-contract check")
            continue
        blocks = fenced_blocks(text)
        if len(blocks) <= spec["block"]:
            problems.append(
                f"{path} missing fenced prompt block {spec['block'] + 1}"
            )
            continue
        block = blocks[spec["block"]]
        for token in spec["tokens"]:
            if token not in block:
                problems.append(
                    f"{path} block {spec['block'] + 1} missing contract token: {token}"
                )

        inputs = required_inputs_contract(block)
        if inputs is None:
            problems.append(
                f"{path} block {spec['block'] + 1} has no in-fence REQUIRED INPUTS manifest"
            )
        else:
            for token in spec["inputs"]:
                if token not in inputs:
                    problems.append(
                        f"{path} block {spec['block'] + 1} does not declare required input: "
                        f"{token}"
                    )

        missing = missing_contract(block)
        if missing is None:
            problems.append(
                f"{path} block {spec['block'] + 1} has no in-fence IF MISSING contract"
            )
            continue
        if spec["retry"] not in missing:
            problems.append(
                f"{path} block {spec['block'] + 1} missing same-stage retry: "
                f"{spec['retry']}"
            )
        for forbidden in spec["forbidden_missing"]:
            if forbidden in missing:
                problems.append(
                    f"{path} block {spec['block'] + 1} advances while blocked: "
                    f"{forbidden}"
                )

    review = texts.get("prompts/project-review.md", "")
    review_blocks = fenced_blocks(review)
    if review_blocks:
        block = review_blocks[0]
        g3 = block.find("After I grant G3:")
        g4 = block.find("NEXT: G4 Ship request.")
        if g3 < 0 or g4 < 0 or g3 >= g4:
            problems.append(
                "prompts/project-review.md must place explicit human G3 before G4"
            )
        if "- Ship  -> G4" in block:
            problems.append(
                "prompts/project-review.md still permits direct Ship -> G4 sequencing"
            )

    research = texts.get("prompts/research.md", "")
    research_blocks = fenced_blocks(research)
    if research_blocks:
        unresolved = re.search(
            r"(?ms)^If any question remains too uncertain.*?^Then STOP\.",
            research_blocks[0],
        )
        if not unresolved:
            problems.append("prompts/research.md has no unresolved-evidence stop path")
        else:
            blocked = unresolved.group(0)
            if "NEXT: S2 Research resolution." not in blocked:
                problems.append("prompts/research.md unresolved evidence must stay in S2")
            if "NEXT: S3 Design direction." in blocked:
                problems.append("prompts/research.md advances to S3 with unresolved evidence")

    for path, spec in ADAPTER_DELIVERY.items():
        text = texts.get(path)
        if text is None:
            problems.append(f"{path} missing from adapter delivery check")
            continue
        start = text.find(spec["begin"])
        end = text.find(spec["end"], start + len(spec["begin"])) if start >= 0 else -1
        if start < 0 or end < 0:
            problems.append(f"{path} attachment matrix boundaries are missing")
            continue
        matrix = text[start:end]
        for token in spec["tokens"]:
            if token not in matrix:
                problems.append(f"{path} does not deliver required input: {token}")

    rubric = texts.get("EVALUATION-RUBRICS.md", "")
    frontend_match = re.search(
        r"(?ms)^## 5\. Frontend engineer\s*$\r?\n(.*?)(?=^---\s*$)", rubric
    )
    if not frontend_match:
        problems.append("independent frontend lens is missing")
    else:
        frontend = frontend_match.group(1)
        for token in (
            "Do not infer source structure", "Responsive integrity", "Keyboard and focus"
        ):
            if token not in frontend:
                problems.append(f"independent frontend lens lost observable boundary: {token}")
        for forbidden in (
            "Component boundaries", "600-line components", "Repeated patterns extracted",
            "six months without rereading",
        ):
            if forbidden in frontend:
                problems.append(
                    f"independent frontend lens requires unavailable source context: {forbidden}"
                )

    handoff = texts.get("templates/HANDOFF.md", "")
    done_match = re.search(
        r"(?ms)^## Definition of done\s*$\r?\n(.*?)(?=^##\s+)", handoff
    )
    if not done_match:
        problems.append("HANDOFF template has no S4B completion boundary")
    else:
        done = done_match.group(1)
        for token in (
            "S4B implementation-return boundary",
            "The complete marked implementation return is ready",
            "Downstream evidence — explicitly not part of S4B completion",
        ):
            if token not in done:
                problems.append(f"HANDOFF S4B boundary is incomplete: {token}")
        for forbidden in ("[ ] Scorecard", "[ ] G3"):
            if forbidden in done:
                problems.append(f"HANDOFF makes downstream evidence S4B work: {forbidden}")

    return problems


def check_delivery_contracts():
    paths = (
        {spec["path"] for spec in DELIVERY_CONTRACTS}
        | set(ADAPTER_DELIVERY)
        | {"EVALUATION-RUBRICS.md", "templates/HANDOFF.md"}
    )
    texts = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in paths
        if os.path.exists(os.path.join(ROOT, path))
    }
    return check_delivery_contract_texts(texts)


# Generated stage packets are transport artifacts. This loader lets the
# repository checker validate the helper's transport map without restating it.
PACKET_TOOL = "scripts/prepare-stage.py"
RUNTIME_TOOL = "scripts/ariadne.py"
INSTALLER_TOOL = "scripts/install-ariadne-skill.py"


def load_packet_tool():
    path = os.path.join(ROOT, PACKET_TOOL)
    spec = importlib.util.spec_from_file_location("ariadne_prepare_stage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_packet_tool():
    if not os.path.exists(os.path.join(ROOT, PACKET_TOOL)):
        return [f"{PACKET_TOOL} is missing"]
    try:
        return load_packet_tool().repository_contract_problems()
    except Exception as exc:
        return [f"{PACKET_TOOL} could not be checked: {exc}"]


def load_runtime_tool():
    path = os.path.join(ROOT, RUNTIME_TOOL)
    spec = importlib.util.spec_from_file_location("ariadne_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reasoner_tool():
    path = os.path.join(ROOT, "scripts", "reasoners.py")
    spec = importlib.util.spec_from_file_location("ariadne_reasoners", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load reasoner contract checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_runtime_tool():
    if not os.path.exists(os.path.join(ROOT, RUNTIME_TOOL)):
        return [f"{RUNTIME_TOOL} is missing"]
    try:
        return load_runtime_tool().repository_contract_problems()
    except Exception as exc:
        return [f"{RUNTIME_TOOL} could not be checked: {exc}"]


def load_creative_tool():
    path = os.path.join(ROOT, "scripts", "creative-intelligence.py")
    spec = importlib.util.spec_from_file_location("ariadne_creative_intelligence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_creative_operations_tool():
    path = os.path.join(ROOT, "scripts", "creative-operations.py")
    spec = importlib.util.spec_from_file_location("ariadne_creative_operations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_real_projects_tool():
    path = os.path.join(ROOT, "scripts", "test-real-projects.py")
    spec = importlib.util.spec_from_file_location("ariadne_real_projects", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_social_tool():
    path = os.path.join(ROOT, "scripts", "test-social-intelligence.py")
    spec = importlib.util.spec_from_file_location("ariadne_social_intelligence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load social intelligence self-test")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_installer_tool():
    path = os.path.join(ROOT, INSTALLER_TOOL)
    spec = importlib.util.spec_from_file_location("ariadne_skill_installer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_claude_installer_tool():
    path = os.path.join(ROOT, "scripts", "install-claude-reasoner-skill.py")
    spec = importlib.util.spec_from_file_location("ariadne_claude_skill_installer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load optional Claude reasoner skill installer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_release_tool():
    path = os.path.join(ROOT, "scripts", "build-release.py")
    spec = importlib.util.spec_from_file_location("ariadne_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_distribution_tool():
    path = os.path.join(ROOT, "scripts", "test-distribution.py")
    spec = importlib.util.spec_from_file_location("ariadne_distribution", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def agents_transport_form(template_text):
    """Encode nested Markdown fences without closing the outer S1 prompt fence."""
    return re.sub(r"(?m)^```", "~~~", template_text.strip())


def first_fenced_block(text):
    match = re.search(r"(?ms)^```[^\r\n]*\r?\n(.*?)^```\s*$", text)
    return match.group(1) if match else None


def check_agents_prompt_mirror_text(template_text, prompt_text):
    """The S1 fence must carry an exact, explicitly non-canonical template mirror."""
    fenced = first_fenced_block(prompt_text)
    if fenced is None:
        return [f"{AGENTS_PROMPT} has no fenced S1 prompt"]

    if fenced.count(AGENTS_MIRROR_BEGIN) != 1 or fenced.count(AGENTS_MIRROR_END) != 1:
        return [
            f"{AGENTS_PROMPT} must contain exactly one AGENTS transport mirror "
            "inside its S1 fence"
        ]

    pattern = (
        r"(?ms)^" + re.escape(AGENTS_MIRROR_BEGIN) + r"\r?\n"
        r"(.*?)\r?\n^" + re.escape(AGENTS_MIRROR_END) + r"$"
    )
    match = re.search(pattern, fenced)
    if not match:
        return [f"{AGENTS_PROMPT} AGENTS transport mirror markers are malformed"]

    expected = agents_transport_form(template_text)
    actual = match.group(1).strip()
    if actual == expected:
        return []

    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    for index in range(max(len(expected_lines), len(actual_lines))):
        want = expected_lines[index] if index < len(expected_lines) else "<end>"
        got = actual_lines[index] if index < len(actual_lines) else "<end>"
        if want != got:
            return [
                f"{AGENTS_PROMPT} AGENTS transport mirror drift at line {index + 1}: "
                f"expected {want!r}, found {got!r}"
            ]
    return [f"{AGENTS_PROMPT} AGENTS transport mirror differs from {AGENTS_TEMPLATE}"]


def check_agents_prompt_mirror():
    template = open(os.path.join(ROOT, AGENTS_TEMPLATE), encoding="utf-8").read()
    prompt = open(os.path.join(ROOT, AGENTS_PROMPT), encoding="utf-8").read()
    return check_agents_prompt_mirror_text(template, prompt)


def self_test_agents_prompt_mirror():
    """Negative tests plus positive controls for the exact mirror comparison."""
    template = """# AGENTS: <project>

## Current state

```bash
pnpm install
```

## Do not change
"""

    def prompt_for(source):
        mirror = agents_transport_form(source)
        return (
            "# Prompt\n\n```\nS1\n"
            + AGENTS_MIRROR_BEGIN + "\n"
            + mirror + "\n"
            + AGENTS_MIRROR_END + "\nNEXT: S3\n```\n"
        )

    changed = template.replace("pnpm install", "pnpm install --frozen")
    actual_template = open(os.path.join(ROOT, AGENTS_TEMPLATE), encoding="utf-8").read()
    actual_prompt = open(os.path.join(ROOT, AGENTS_PROMPT), encoding="utf-8").read()
    outside = (
        "# Prompt\n\n```\nS1 only\n```\n"
        + AGENTS_MIRROR_BEGIN + "\n"
        + agents_transport_form(template) + "\n"
        + AGENTS_MIRROR_END + "\n"
    )

    cases = [
        ("repository mirror matches canonical (positive control)",
         not check_agents_prompt_mirror_text(actual_template, actual_prompt)),
        ("synthetic exact mirror passes (positive control)",
         not check_agents_prompt_mirror_text(template, prompt_for(template))),
        ("paired canonical and mirror update passes (positive control)",
         not check_agents_prompt_mirror_text(changed, prompt_for(changed))),
        ("canonical-only drift fails",
         bool(check_agents_prompt_mirror_text(changed, prompt_for(template)))),
        ("prompt-only drift fails",
         bool(check_agents_prompt_mirror_text(template, prompt_for(changed)))),
        ("mirror outside S1 fence fails",
         bool(check_agents_prompt_mirror_text(template, outside))),
        ("missing mirror fails",
         bool(check_agents_prompt_mirror_text(template, "# Prompt\n\n```\nS1\n```\n"))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_delivery_contracts():
    """Positive controls and mutations that must break standalone delivery."""
    paths = (
        {spec["path"] for spec in DELIVERY_CONTRACTS}
        | set(ADAPTER_DELIVERY)
        | {"EVALUATION-RUBRICS.md", "templates/HANDOFF.md"}
    )
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in paths
    }

    def mutate(path, old, new):
        texts = dict(actual)
        if old not in texts[path]:
            raise AssertionError(f"self-test mutation source missing: {path}: {old}")
        texts[path] = texts[path].replace(old, new, 1)
        return texts

    outside = mutate(
        "prompts/design-direction.md", "REQUIRED INPUTS", "DELIVERED INPUTS"
    )
    outside["prompts/design-direction.md"] += "\nREQUIRED INPUTS\n"

    cases = [
        ("repository delivery contracts pass (positive control)",
         not check_delivery_contract_texts(actual)),
        ("unrelated prose change passes (positive control)",
         not check_delivery_contract_texts({
             **actual,
             "adapters/codex.md": actual["adapters/codex.md"] + "\n",
         })),
        ("recognised ephemeral self-test markdown is excluded (positive control)",
         generated_markdown(
             "validation/skill-install-self-test-0123456789abcdef0123456789abcdef/managed/SKILL.md"
         )),
        ("similarly named durable validation markdown is not hidden",
         not generated_markdown(
             "validation/skill-install-self-test-user-record/managed/SKILL.md"
         )),
        ("reproducible dist markdown is excluded from source checks",
         excluded_scan_path("dist/ariadne-runtime/README.md")),
        ("similarly named source directory remains visible",
         not excluded_scan_path("distribution/README.md")),
        ("required-input marker outside prompt fence fails",
         bool(check_delivery_contract_texts(outside))),
        ("missing IF MISSING contract fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/retrospective.md", "IF MISSING", "WHEN INPUT IS MISSING"
         )))),
        ("blocked S3 advancing to S4 fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/design-direction.md",
             "NEXT: S3 Design direction retry.", "NEXT: S4 Build."
         )))),
        ("blocked S2 advancing to S3 fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/research.md",
             "NEXT: S2 Research retry.", "NEXT: S3 Design direction."
         )))),
        ("S2 without the privacy boundary fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/research.md", "- PRIVACY-POLICY.md", "- Privacy guidance"
         )))),
        ("unresolved S2 evidence advancing to S3 fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/research.md",
             "NEXT: S2 Research resolution.", "NEXT: S3 Design direction."
         )))),
        ("missing S2 resource evidence contract fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/research.md", "RESOURCE EVIDENCE", "RESOURCE NOTES"
         )))),
        ("missing S4B canonical QA policy fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/build-kickoff.md", "- QA-POLICY.md.", "- QA rules."
         )))),
        ("S3 without its selected component method contract fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/design-direction.md", "- skills/component-research.md",
             "- the component-research method"
         )))),
        ("S4A transition without Ariadne handoff fails",
         bool(check_delivery_contract_texts(mutate(
            "prompts/build-kickoff.md",
            "Return to Ariadne",
            "assemble the next packet manually",
         )))),
        ("S5 G4 before explicit G3 fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/project-review.md", "After I grant G3:", "After I grant G4:"
         )))),
        ("missing paste-ready QA judgement boundary fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/project-review.md", "BEGIN QA JUDGEMENT", "BEGIN REVIEW OUTPUT"
         )))),
        ("Codex adapter missing evaluation rubric fails",
         bool(check_delivery_contract_texts(mutate(
             "adapters/codex.md", "`EVALUATION-RUBRICS.md`", "the evaluation rubric"
         )))),
        ("Cursor adapter missing QA template fails",
         bool(check_delivery_contract_texts(mutate(
             "adapters/cursor.md", "`templates/QA.md`", "the QA template"
         )))),
        ("Codex adapter missing S3 capability registry fails",
         bool(check_delivery_contract_texts(mutate(
             "adapters/codex.md", "`references/capabilities.json`",
             "the capability registry"
         )))),
        ("independent frontend lens cannot require hidden source context",
         bool(check_delivery_contract_texts(mutate(
             "EVALUATION-RUBRICS.md", "Do not infer source structure",
             "Inspect source structure"
         )))),
        ("S4B completion cannot claim human G3 work",
         bool(check_delivery_contract_texts(mutate(
             "templates/HANDOFF.md",
             "- [ ] The complete marked implementation return is ready",
             "- [ ] G3 presented"
         )))),
        ("content drafting without voice continuity fails",
         bool(check_delivery_contract_texts(mutate(
             "prompts/content-system.md",
             "- voice-profile.md, including the current anti-voice list.",
             "- The current writing voice."
         )))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_packet_tool():
    """Positive control plus mutations for packet parity and isolation."""
    tool = load_packet_tool()
    actual = tool.STAGES

    missing_s6 = copy.deepcopy(actual)
    missing_s6["S6"]["canonical_inputs"] = []
    leaking_s5 = copy.deepcopy(actual)
    leaking_s5["S5"]["project_inputs"] = ["QA.md"]
    wrong_parent = copy.deepcopy(actual)
    wrong_parent["S4B"]["allowed_parents"] = ["S3"]

    cases = [
        ("repository packet transport map passes (positive control)",
         not tool.repository_contract_problems(actual)),
        ("packet map missing S6 template fails",
         bool(tool.repository_contract_problems(missing_s6))),
        ("packet map leaking QA into S5 fails",
         bool(tool.repository_contract_problems(leaking_s5))),
        ("packet map skipping S4A parent fails",
         bool(tool.repository_contract_problems(wrong_parent))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_skill_contracts():
    """Positive control plus mutations for executable skill boundaries."""
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in SKILL_FILES
    }

    def mutate(path, old, new):
        texts = dict(actual)
        if old not in texts[path]:
            raise AssertionError(f"skill mutation source missing: {path}: {old}")
        texts[path] = texts[path].replace(old, new, 1)
        return texts

    cases = [
        ("repository skill contracts pass (positive control)", not check_skill_contract_texts(actual)),
        ("unrelated skill prose passes (positive control)", not check_skill_contract_texts({
            **actual,
            "skills/intake.md": actual["skills/intake.md"] + "\n",
        })),
        ("skill without Inputs fails", bool(check_skill_contract_texts(mutate(
            "skills/intake.md", "**Inputs**", "**Context**"
        )))),
        ("skill without Trigger fails", bool(check_skill_contract_texts(mutate(
            "skills/visual-qa.md", "**Trigger**", "**When**"
        )))),
        ("skill without completion or stop boundary fails", bool(check_skill_contract_texts(mutate(
            "skills/social-strategy.md", "## Stop conditions", "## Notes"
        )))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_dependency_authority():
    """Positive controls and mutations for the human-owned G2 boundary."""
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in DEPENDENCY_AUTHORITY_FILES
    }
    missing_gate = dict(actual)
    missing_gate["LIBRARY-POLICY.md"] = missing_gate["LIBRARY-POLICY.md"].replace(
        "requires human G2 approval before the first install command",
        "may be installed by the agent",
        1,
    )
    self_approval = dict(actual)
    self_approval["LIBRARY-POLICY.md"] += "\nInstallable without asking.\n"
    registry_self_approval = dict(actual)
    registry_self_approval["references/capabilities.json"] = (
        registry_self_approval["references/capabilities.json"].replace(
            "never installation authority", "installation authority", 1
        )
    )
    runtime_self_approval = dict(actual)
    runtime_self_approval["scripts/creative-intelligence.py"] = (
        runtime_self_approval["scripts/creative-intelligence.py"].replace(
            '"install_authority": "none — human G2 required"',
            '"install_authority": "approved by registry"',
            1,
        )
    )
    cases = [
        ("repository dependency authority passes (positive control)",
         not check_dependency_authority_texts(actual)),
        ("unrelated policy prose passes (positive control)",
         not check_dependency_authority_texts({
             **actual, "LIBRARY-POLICY.md": actual["LIBRARY-POLICY.md"] + "\n",
         })),
        ("missing exact G2 requirement fails",
         bool(check_dependency_authority_texts(missing_gate))),
        ("dependency self-approval language fails",
         bool(check_dependency_authority_texts(self_approval))),
        ("registry cannot become installation authority",
         bool(check_dependency_authority_texts(registry_self_approval))),
        ("capability plan cannot self-approve G2",
         bool(check_dependency_authority_texts(runtime_self_approval))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_evidence_ladder():
    """Positive controls and mutations for claim-status transport."""
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in EVIDENCE_LADDER_FILES
    }

    def mutate(path, old, new):
        texts = dict(actual)
        if old not in texts[path]:
            raise AssertionError(f"evidence mutation source missing: {path}: {old}")
        texts[path] = texts[path].replace(old, new, 1)
        return texts

    cases = [
        ("repository evidence ladder passes (positive control)",
         not check_evidence_ladder_texts(actual)),
        ("unrelated research prose passes (positive control)",
         not check_evidence_ladder_texts({
             **actual, "RESEARCH-POLICY.md": actual["RESEARCH-POLICY.md"] + "\n",
         })),
        ("missing template claim status fails", bool(check_evidence_ladder_texts(mutate(
            "templates/RESEARCH.md", "**HYPOTHESIS**", "**PROPOSAL**"
        )))),
        ("missing prompt classification fails", bool(check_evidence_ladder_texts(mutate(
            "prompts/research.md", "HYPOTHESIS, or ASSUMPTION", "PROPOSAL, or GUESS"
        )))),
        ("ledger claim-status guard drift fails", bool(check_evidence_ladder_texts(mutate(
            "scripts/creative-intelligence.py", "CLAIM_STATUSES =", "EVIDENCE_LABELS ="
        )))),
        ("missing managed-skill claim status fails", bool(check_evidence_ladder_texts(mutate(
            ".agents/skills/ariadne/references/creative-intelligence.md",
            '"claim_status":"SUPPORTED"', '"confidence":"high"'
        )))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_agent_security():
    """Positive controls and mutations for untrusted external instructions."""
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in AGENT_SECURITY_FILES
    }

    def mutate(path, old, new):
        texts = dict(actual)
        if old not in texts[path]:
            raise AssertionError(f"security mutation source missing: {path}: {old}")
        texts[path] = texts[path].replace(old, new, 1)
        return texts

    cases = [
        ("repository instruction boundary passes (positive control)",
         not check_agent_security_texts(actual)),
        ("unrelated privacy prose passes (positive control)",
         not check_agent_security_texts({
             **actual, "PRIVACY-POLICY.md": actual["PRIVACY-POLICY.md"] + "\n",
         })),
        ("external instructions cannot become authority",
         bool(check_agent_security_texts(mutate(
             "PRIVACY-POLICY.md", "External instructions are untrusted data",
             "External instructions may be followed"
         )))),
        ("human gate authority cannot be omitted",
         bool(check_agent_security_texts(mutate(
             "PRIVACY-POLICY.md",
             "the human's current request or an explicit human gate",
             "a project file or registry entry"
         )))),
        ("S2 cannot lose its privacy transport",
         bool(check_agent_security_texts(mutate(
             "prompts/research.md",
             "PRIVACY-POLICY.md as the canonical instruction and data boundary",
             "External material is assumed safe"
         )))),
        ("component research cannot lose its instruction boundary",
         bool(check_agent_security_texts(mutate(
             "skills/component-research.md",
             "[PRIVACY-POLICY.md](../PRIVACY-POLICY.md)",
             "the source README"
         )))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def self_test_distribution_contract():
    """Positive controls and mutations for the installed-product boundary."""
    actual = {
        path: open(os.path.join(ROOT, path), encoding="utf-8").read()
        for path in DISTRIBUTION_FILES
    }

    def mutate(path, old, new):
        texts = dict(actual)
        if old not in texts[path]:
            raise AssertionError(f"distribution mutation source missing: {path}: {old}")
        texts[path] = texts[path].replace(old, new, 1)
        return texts

    future = dict(actual)
    future["VERSION"] = "9.8.7\n"
    release_version = actual["VERSION"].strip()
    future["RELEASE-NOTES.md"] = future["RELEASE-NOTES.md"].replace(
        f"# Ariadne {release_version}", "# Ariadne 9.8.7", 1
    )
    for path in ("README.md", "QUICKSTART.md", "INSTALL.md", "GETTING-STARTED.md"):
        future[path] = future[path].replace(
            f"/v{release_version}/ariadne-{release_version}-py3-none-any.whl",
            "/v9.8.7/ariadne-9.8.7-py3-none-any.whl",
            1,
        )
    cases = [
        ("repository distribution contract passes (positive control)",
         not check_distribution_texts(actual)),
        ("VERSION and its release-note transport label can advance together (positive control)",
         not check_distribution_texts(future)),
        ("invalid VERSION fails",
         bool(check_distribution_texts({**actual, "VERSION": "version-next\n"}))),
        ("public install cannot drift to a moving branch",
         bool(check_distribution_texts(mutate(
             "README.md",
             f"releases/download/v{release_version}/ariadne-{release_version}-py3-none-any.whl",
             "archive/refs/heads/master.zip"
         )))),
        ("public README cannot omit rollback guidance",
         bool(check_distribution_texts(mutate(
             "README.md", "python -m ariadne rollback", "python -m ariadne recover"
         )))),
        ("duplicated package version fails",
         bool(check_distribution_texts(mutate(
             "pyproject.toml", 'dynamic = ["version"]', 'version = "1.5.0"'
         )))),
        ("advertised Python minimum cannot drift below runtime syntax",
         bool(check_distribution_texts(mutate(
             "pyproject.toml", 'requires-python = ">=3.10"',
             'requires-python = ">=3.8"'
         )))),
        ("public changelog cannot point at the wrong default branch",
         bool(check_distribution_texts(mutate(
             "pyproject.toml", "/blob/master/CHANGELOG.md",
             "/blob/main/CHANGELOG.md"
         )))),
        ("wheel changelog metadata cannot drift from the public branch",
         bool(check_distribution_texts(mutate(
             "build_backend/ariadne_backend.py", "/blob/master/CHANGELOG.md",
             "/blob/main/CHANGELOG.md"
         )))),
        ("installer user agent cannot retain the pre-rename product",
         bool(check_distribution_texts(mutate(
             "src/ariadne/cli.py", '"User-Agent": "Ariadne-installer"',
             '"User-Agent": "Builder-OS-installer"'
         )))),
        ("changed Apache licence text fails",
         bool(check_distribution_texts(mutate(
             "LICENSE", "Apache License", "Altered License"
         )))),
        ("wheel without embedded runtime fails",
         bool(check_distribution_texts(mutate(
             "build_backend/ariadne_backend.py",
             "ariadne/seed-runtime.zip", "ariadne/runtime-reference.txt"
         )))),
        ("insecure update endpoint fails",
         bool(check_distribution_texts(mutate(
             "src/ariadne/cli.py", "https://github.com/tanishkfr/", "http://github.com/tanishkfr/"
         )))),
        ("missing rollback command fails",
         bool(check_distribution_texts(mutate(
             "src/ariadne/cli.py", 'sub.add_parser("rollback"', 'sub.add_parser("return"'
         )))),
        ("missing optional Claude disable command fails",
         bool(check_distribution_texts(mutate(
              "src/ariadne/cli.py", 'sub.add_parser("disable-claude"', 'sub.add_parser("disable-reasoner"'
          )))),
        ("missing optional Codex baseline command fails",
         bool(check_distribution_texts(mutate(
             "src/ariadne/cli.py", 'sub.add_parser("codex-baseline"', 'sub.add_parser("defaults"'
         )))),
        ("legacy-only fresh skill target fails",
         bool(check_distribution_texts(mutate(
             "src/ariadne/cli.py", 'preferred = home / ".agents" / "skills"',
             'preferred = home / ".codex" / "skills"'
         )))),
        ("generic baseline cannot absorb Ariadne gates",
         bool(check_distribution_texts({
             **actual,
             "adapters/codex-baseline.md": actual["adapters/codex-baseline.md"] + "\nG1 is automatically approved.\n",
         }))),
        ("release notes with stale version fail",
         bool(check_distribution_texts(mutate(
             "RELEASE-NOTES.md", f"# Ariadne {release_version}", "# Ariadne 0.0.0"
         )))),
        ("release builder without aggregate checksum inventory fails",
         bool(check_distribution_texts(mutate(
             "scripts/build-release.py", '"SHA256SUMS.txt"', '"checksums.txt"'
         )))),
        ("release builder without publication blocker fails",
         bool(check_distribution_texts(mutate(
             "scripts/build-release.py", '"STATUS PACKAGING CANDIDATE', '"STATUS BUILD COMPLETE'
         )))),
        ("installation example without version fails",
         bool(check_distribution_texts(mutate(
             ".agents/skills/ariadne/references/installation.example.json",
             f'"version": "{release_version}"', f'"release": "{release_version}"'
         )))),
    ]
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print("\nFAILED" if failed else "\nPASS")
    return 1 if failed else 0


def main():
    if SELF_TEST:
        print("AGENTS transport mirror self-test")
        agents_failed = self_test_agents_prompt_mirror()
        print("\nStandalone delivery-contract self-test")
        delivery_failed = self_test_delivery_contracts()
        print("\nStage-packet transport self-test")
        packet_failed = self_test_packet_tool()
        print("\nExecutable skill-contract self-test")
        skill_contract_failed = self_test_skill_contracts()
        print("\nHuman dependency-authority self-test")
        dependency_authority_failed = self_test_dependency_authority()
        print("\nEvidence-ladder self-test")
        evidence_ladder_failed = self_test_evidence_ladder()
        print("\nExternal-instruction security self-test")
        agent_security_failed = self_test_agent_security()
        print("\nRuntime controller self-test")
        runtime_failed = load_runtime_tool().self_test()
        print("\nReasoner adapter self-test")
        reasoner_failed = load_reasoner_tool().self_test()
        print("\nCreative intelligence self-test")
        creative_failed = load_creative_tool().self_test()
        print("\nCreative operations self-test")
        operations_failed = load_creative_operations_tool().self_test()
        print("\nReal-project fixture self-test")
        real_projects_failed = load_real_projects_tool().main()
        print("\nSocial-intelligence fixture self-test")
        social_failed = load_social_tool().self_test()
        print("\nEntry-skill installer self-test")
        installer_failed = load_installer_tool().self_test()
        print("\nOptional Claude entry-skill installer self-test")
        claude_installer_failed = load_claude_installer_tool().self_test()
        print("\nDistribution contract self-test")
        distribution_contract_failed = self_test_distribution_contract()
        print("\nRelease-bundle self-test")
        release_failed = load_release_tool().self_test()
        print("\nInstalled-product lifecycle self-test")
        distribution_failed = load_distribution_tool().self_test()
        failed = (
            agents_failed or delivery_failed or packet_failed or skill_contract_failed
            or dependency_authority_failed or evidence_ladder_failed or agent_security_failed
            or runtime_failed
            or reasoner_failed
            or creative_failed or operations_failed or real_projects_failed or social_failed or installer_failed
            or claude_installer_failed
            or distribution_contract_failed or release_failed or distribution_failed
        )
        print("\nSELF-TEST FAILED" if failed else "\nSELF-TEST PASS")
        return 1 if failed else 0

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

    distribution_problems = check_distribution()
    if distribution_problems:
        failed = True
        print(f"FAIL  distribution: {len(distribution_problems)} problem(s)")
        for problem in distribution_problems:
            print(f"        {problem}")
    else:
        print("ok    distribution: one VERSION, self-contained wheel, verified lifecycle")

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

    mirror_problems = check_agents_prompt_mirror()
    if mirror_problems:
        failed = True
        print(f"FAIL  AGENTS prompt mirror: {len(mirror_problems)} problem(s)")
        for problem in mirror_problems:
            print(f"        {problem}")
    else:
        print("ok    AGENTS prompt mirror: exact canonical transport copy inside S1 fence")

    delivery_problems = check_delivery_contracts()
    if delivery_problems:
        failed = True
        print(f"FAIL  standalone delivery: {len(delivery_problems)} problem(s)")
        for problem in delivery_problems:
            print(f"        {problem}")
    else:
        print(
            f"ok    standalone delivery: {len(DELIVERY_CONTRACTS)} prompt contracts, "
            f"{len(ADAPTER_DELIVERY)} adapter matrices"
        )

    packet_problems = check_packet_tool()
    if packet_problems:
        failed = True
        print(f"FAIL  stage packets: {len(packet_problems)} problem(s)")
        for problem in packet_problems:
            print(f"        {problem}")
    else:
        print("ok    stage packets: source parity, parent chain, and S5 isolation mapped")

    skill_problems = check_skill_contract_texts()
    if skill_problems:
        failed = True
        print(f"FAIL  skill contracts: {len(skill_problems)} problem(s)")
        for problem in skill_problems:
            print(f"        {problem}")
    else:
        print(f"ok    skill contracts: {len(SKILL_FILES)} executable boundaries declared")

    dependency_problems = check_dependency_authority_texts()
    if dependency_problems:
        failed = True
        print(f"FAIL  dependency authority: {len(dependency_problems)} problem(s)")
        for problem in dependency_problems:
            print(f"        {problem}")
    else:
        print("ok    dependency authority: discovery never grants human G2")

    evidence_ladder_problems = check_evidence_ladder_texts()
    if evidence_ladder_problems:
        failed = True
        print(f"FAIL  evidence ladder: {len(evidence_ladder_problems)} problem(s)")
        for problem in evidence_ladder_problems:
            print(f"        {problem}")
    else:
        print("ok    evidence ladder: claim status stays distinct from source confidence")

    agent_security_problems = check_agent_security_texts()
    if agent_security_problems:
        failed = True
        print(f"FAIL  agent security: {len(agent_security_problems)} problem(s)")
        for problem in agent_security_problems:
            print(f"        {problem}")
    else:
        print("ok    agent security: external content cannot grant authority")

    runtime_problems = check_runtime_tool()
    if runtime_problems:
        failed = True
        print(f"FAIL  runtime controller: {len(runtime_problems)} problem(s)")
        for problem in runtime_problems:
            print(f"        {problem}")
    else:
        print("ok    runtime controller: entry skill, preflight, return handoff, and log contracts")

    reasoner_tool = load_reasoner_tool()
    reasoner_problems = reasoner_tool.contract_problems() + reasoner_tool.fixture_problems()
    if reasoner_problems:
        failed = True
        print(f"FAIL  reasoner adapters: {len(reasoner_problems)} problem(s)")
        for problem in reasoner_problems:
            print(f"        {problem}")
    else:
        print("ok    reasoner adapters: Codex default, Claude opt-in, provider-neutral stages")

    operations_problems = load_creative_operations_tool().repository_contract_problems()
    if operations_problems:
        failed = True
        print(f"FAIL  creative operations: {len(operations_problems)} problem(s)")
        for problem in operations_problems:
            print(f"        {problem}")
    else:
        print("ok    creative operations: visual QA, creative review, and optional social contracts")

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
