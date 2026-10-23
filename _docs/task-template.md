# Task Grooming Template

> Use this template when grooming a raw GitHub Issue before handing it to the Software Engineer subagent.
> Every section is mandatory. Do not open a PR until all four sections are filled and the Definition of Done (below) is met.

---

## Goal

One or two sentences defining the precise functional state of the system upon completion of this task, naming the MVP scope plan goal (G-xx) it advances and the delivery phase (P0–P5) it belongs to.

_Example: "The `assemble.py` script copies the master template and deletes all non-selected block ranges, satisfying G-05 (correct selection) as part of phase P3."_

---

## Acceptance criteria

Each criterion is a **binary pass/fail statement** verifiable on-screen, via the script's JSON stdout, or in automated test output. No criterion may require human judgment to evaluate.

- [ ] **[criterion 1]** — _State the exact observable evidence: e.g. "Running `pytest tests/unit/test_prune.py -v` exits 0 and all parameterised boundary cases (0, 1, 2, typical, max=60, max+1=61 blocks) pass."_
- [ ] **[criterion 2]** — _Edge / boundary condition: e.g. "`assemble.py` exits 1 with `{"error": {"code": "marker_error", ...}}` on stdout when the master contains an unbalanced block marker."_
- [ ] **[criterion 3]** — _Contract / schema check: e.g. "The JSON stdout of `assemble.py --dry-run` validates against `schemas/job.schema.json` with zero `jsonschema` errors."_
- [ ] **[criterion 4]** — _Safety invariant: e.g. "After a failed run, the master template's Drive revision ID is unchanged (G-08)."_

_Add or remove criteria as needed. Every criterion must cite which goal (G-xx), decision (AD-xx, SB-xx, TL-xx) or non-functional bound (NF-xx) it verifies._

---

## Out of scope

Features or refactorings discovered during grooming that are **not** required for this task. Each item must be linked to a follow-up GitHub Issue (file one if it doesn't exist yet).

- _[Feature or concern] — deferred to GitHub Issue #NUMBER. Reason: [why it is not part of this task]._
- _MVP non-goals from scope plan §3.1 are cited here if raised, not reopened._

_If nothing is out of scope, write "Nothing identified."_

---

## Constraints

### File boundaries
- Allowed to create or modify: _[list paths or patterns from `_docs/architecture.md` §3 that this task touches]_
- Must NOT modify: master templates, block registry files, published recipes, `_docs/MVP_scope_plan.md`, or any file outside the above list.

### Libraries and patterns
- Permitted dependencies: _[list from `requirements.txt`; justify any new addition in the issue before adding it]_
- Prohibited: any library that makes live Google API calls in unit tests; any hardcoded file IDs or credentials.

### Architectural rules (cite scope plan ID)
- No credentials in code, tests, or logs (SB-02).
- No writes to master templates (AD-11).
- No live Google API calls in unit or integration tests — use fakes or mocks (architecture §9).
- Delete block ranges in descending index order in a single `batchUpdate` (TL-01).
- All error codes must match the table in `_docs/architecture.md` §4 (G-02, §6.2).
- Exponential backoff on transient API errors; max 5 retries (NF-06).
- Every ledger record carries `workspace_id` (AD-13).

### Safety rules
- Never log document content, placeholder values, or PII (SB-06).
- Never use the production Shared Drive or real customer data in tests (SB-05).
- Never close a GitHub Issue directly (process rule — only the Orchestrator closes issues).

---

## Definition of Done

The issue is ready to hand to the SWE subagent when **all** of the following are true:

- [ ] All four sections above are filled.
- [ ] Every acceptance criterion is a binary pass/fail statement, not a description of implementation.
- [ ] Every requirement cites at least one scope plan ID (G-, AD-, SB-, TL-, NF-).
- [ ] All out-of-scope items link to a follow-up GitHub Issue.
- [ ] An engineer could implement the feature without asking a single clarifying question.
- [ ] No open questions (Q-xx) or VERIFY items are left unresolved that this task depends on; if any exist, the issue is labelled `blocked: question` and grooming stops.
