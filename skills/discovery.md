# SKILL: discovery

**Trigger** — a new project starts, at S1.
**Owner** — Strategist · **Class** — `R1`
**Inputs** — the user's request, any references, the Routing Block
**Output** — [`PROJECT.md`](../templates/PROJECT.md)

Discovery collects. [grilling](grilling.md) stress-tests. Do not merge them: collecting and challenging in the same pass produces defensive answers.

---

## Method

**1. Restate the request in one sentence.** If you cannot, you do not understand it yet. Show the restatement — misunderstandings surface here at zero cost.

**2. Ask the mode's questions.** From [ROUTER.md](../ROUTER.md) section 4. Maximum five, batched, each with a proposed default so the reply can be "all defaults".

**3. Separate goal from scope.** The goal is the outcome. The scope is what gets built. "Get more client enquiries" is a goal; "a five-page site with a contact form" is a scope. Confusing them produces projects that ship and achieve nothing.

**4. Force the non-goals.** Ask directly: *what is this deliberately not?* Non-goals do more work than goals — they are what stops scope inflation at S4 and they are what a router checks a late suggestion against.

Minimum three non-goals. If none come, propose some and get them confirmed.

**5. Make success falsifiable.** "It looks good" cannot fail. "A studio would show it in a portfolio review without apologising" can. Push until a criterion could plausibly be judged not met.

**6. Surface constraints.** Deadline, budget, existing assets, brand rules, technical constraints, who else has approval. Constraints found at S1 are design inputs. The same constraints found at S4 are rework.

**7. Log every assumption.** Anything not asked but proceeding on, phrased so it can be contradicted in one line. See [ROUTER.md](../ROUTER.md) section 5.

**8. Record open questions.** Things that genuinely need an answer but do not block starting. Each gets a "needed by stage" marker.

---

## Done when

You can answer these without hedging:

- What is this?
- Who is it for?
- What is deliberately not in it?
- How will we know it worked?
- What do we not know yet, and when do we need to know it?

If any answer is vague, discovery is not finished. **Vague scope is the root cause of generic design** — a model with no constraint produces the average of everything it has seen. This is the highest-leverage stage in the system and the one most often rushed.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Twenty questions, exhausted user | Five maximum, batched, with defaults |
| Accepting "make it look premium" | Ask what it should be premium *like*, and to whom |
| Skipping non-goals because the project seems small | Small projects inflate fastest; three minimum |
| Success criteria that cannot fail | Rewrite until they could plausibly be judged unmet |
| Discovering an asset gap at S4 | Ask what exists at step 6, every time — see [ROUTER.md](../ROUTER.md) 7.3 |
| Designing during discovery | Note the idea, move on. Direction is S3 and needs research first. |
