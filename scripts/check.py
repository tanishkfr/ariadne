#!/usr/bin/env python3
"""
Builder OS consistency check.

Three deterministic checks that caught real bugs during construction:
  1. Broken internal links
  2. Duplicated sentences (source-of-truth violations)
  3. Required files present

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
    "prompts/project-start.md", "prompts/project-review.md",
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
DUPE_EXEMPT = ("prompts/", "templates/AGENTS.md")


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
