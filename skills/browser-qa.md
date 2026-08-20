# SKILL: browser-qa

**Trigger** — something is running and needs verifying. S5.
**Owner** — QA engineer · **Class** — `R6` first, then `R4`
**Inputs** — a running build or a preview URL
**Output** — [`QA.md`](../templates/QA.md) with evidence per check, and screenshots for G3

Checklist: [QA-POLICY.md](../QA-POLICY.md). This file is how to run it without wasting a day.

---

## The escalation ladder

Cheapest first. **Never skip a rung upward** — each one catches things the next would have spent much longer finding.

```
1. Production build      free, seconds, catches the most
2. Typecheck + lint      free, seconds
3. Playwright script     free, repeatable, runs again tomorrow
4. Browser agent         slow, but sees what a human sees
5. Your own eyes         the only thing that catches "this feels wrong"
```

Rung 4 is where usage disappears. Use it for what only it can do: judging rendered output, catching console errors in real navigation, and testing interactions that are not yet scripted.

**Anything you will check twice becomes a Playwright script.** Writing the script costs about the same as one browser-agent pass and then costs nothing forever.

---

## Method

**1. Run the free checks first** — build, typecheck, lint. If the build fails, everything below is meaningless. See [QA-POLICY.md](../QA-POLICY.md) sections 3.1-3.3.

**2. Load every route and read the console.** Zero errors, zero React warnings. Hydration mismatches are Blocking — they are a real correctness bug, not noise.

**3. Walk the responsive widths:** 375, 768, 900, 1280, 1920. The 900-1100 range breaks more layouts than any other and is the one people skip. Screenshot each.

**4. Exercise every state that is not the happy path.** Empty, loading, error, form validation, offline if relevant. These are where AI-assisted builds are consistently thin, because the happy path is what gets built and demoed.

**5. Test the interactions by hand.** Click, type, tab, submit, cancel, interrupt mid-animation, navigate back. Scroll-triggered work especially: fast scroll, refresh mid-page, back-navigation.

**6. Capture evidence as you go.** A check without a command output, a number, or a screenshot is not a result. Record **not run** honestly rather than leaving a blank or assuming a pass.

**7. Look at the screenshots yourself.** Capturing evidence and checking it are different acts. An agent that screenshots without inspecting has automated the taking of evidence, not the verification.

**8. File findings with severity and a fix.** Severity definitions: [QA-POLICY.md](../QA-POLICY.md) section 2. Findings go back to the Implementer — **the QA role does not fix product code**, because a role that fixes what it finds stops reporting inconvenient findings.

---

## Preview vs localhost

Run performance and font checks on the **deployed preview**, not localhost. Localhost numbers are optimistic to the point of being meaningless — no real network, no CDN, no cold start, warm caches.

The preview is also the only place you catch missing environment variables, broken image optimisation, and anything that quietly depended on a local file.

---

## Done when

Every row in `QA.md` has a state and evidence · screenshots captured and inspected · findings filed with severity and fixes · the Known gaps list is written and not empty.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Marking checks passed without evidence | Evidence rule; "not run" is an honest state |
| Testing only the happy path | Step 4 is a required pass |
| Skipping the 900-1100 range | It is in the width list for a reason |
| Using a browser agent for what a build would answer | The ladder, rung by rung |
| Re-running the same manual check every session | Turn it into a Playwright script |
| QA fixing its own findings | Findings go to the Implementer |
| Performance measured on localhost | Preview only |
