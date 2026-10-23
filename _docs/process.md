# Multi-Agent Workflow Process

> Formalises the orchestration lifecycle for the Template-Driven Document Assembly Engine.
> All agents must read this file before starting any task loop.

---

## 1. State Transition Graph

```
                        ┌─────────────────────┐
                        │   ORCHESTRATOR       │
                        │   (main session)     │
                        └──────────┬───────────┘
                                   │ picks open issue
                    ┌──────────────▼──────────────────┐
                    │   Is it labelled 'human'        │
                    │   or 'blocked: question'?        │
                    └──────┬──────────────────┬────────┘
                          YES                 NO
                           │                  │
                    ┌──────▼──────┐   ┌───────▼────────────┐
                    │  SKIP       │   │  PM SUBAGENT        │
                    │  (human     │   │  Groom the issue    │
                    │  resolves)  │   │  (_docs/team/pm.md) │
                    └─────────────┘   └───────┬────────────┘
                                              │ groomed issue body updated
                                     ┌────────▼────────────┐
                                     │  SWE SUBAGENT        │
                                     │  Implement in        │
                                     │  worktree            │
                                     │  (.worktrees/        │
                                     │   issue-NUMBER)      │
                                     └────────┬────────────┘
                                              │ posts summary comment
                                     ┌────────▼────────────┐
                                     │  QA SUBAGENT         │
                                     │  Fresh context,      │
                                     │  verify behaviour    │
                                     └──┬──────────┬────────┘
                                       FAIL        PASS
                                        │           │
                              ┌─────────▼──┐  ┌────▼────────────────┐
                              │  Loop back │  │  ORCHESTRATOR        │
                              │  to SWE    │  │  Closes issue        │
                              │  (max 3x)  │  │  Removes worktree    │
                              └────────────┘  └─────────────────────┘
                                   │ 3rd FAIL
                          ┌────────▼──────────┐
                          │  Label issue       │
                          │  'needs-human'     │
                          │  Move to next      │
                          └───────────────────┘
```

---

## 2. Human Nodes

The following situations **always** pause the loop and require a human:

| Trigger | Label added | Who resolves |
|---|---|---|
| Issue is tagged `[HUMAN]` in `_docs/tasks.md` | `human` | Relevant human role (R-01 to R-06) |
| Issue depends on an unanswered open question (Q-xx) | `blocked: question` | Requester / Workspace Owner |
| Issue depends on an unconfirmed VERIFY item | `blocked: question` | R-01 or R-04 |
| Any change to `_docs/MVP_scope_plan.md` | Requires human approval before merge | R-02 Workspace Owner |
| Any change to master templates or block registry | Requires human approval before merge | R-03 Content Curator |
| Any change to published recipes | Requires human approval before merge | R-02 or R-04 |
| Three consecutive `QA: FAIL` on one issue | `needs-human` | R-04 Workflow Designer |

Agents **never** merge changes to the above artefacts without explicit human approval.

---

## 3. Subagent Handoff Rules

### 3.1 PM subagent
- Reads the raw GitHub Issue.
- Grooms per `_docs/team/pm.md` and `_docs/task-template.md`.
- Updates the issue body via `gh issue edit`.
- Adds the correct phase label; removes `needs-grooming`.
- Does **not** write code.

### 3.2 SWE subagent
- Works in the issue's worktree (see §5).
- Implements per `_docs/team/software-engineer.md`.
- Runs `pytest tests/unit tests/integration` before posting the summary comment.
- Posts the implementation summary comment **without closing the issue**.
- Does **not** run E2E golden tests (that is QA's job on the sandbox Drive).

### 3.3 QA subagent
- Opens a **fresh context window** — no shared state with the SWE session.
- Verifies per `_docs/team/qa-engineer.md`.
- **Ticks every passing AC checkbox** in the issue body using `gh issue edit <N> --body "..."` with `- [ ]` replaced by `- [x]` for each passing criterion. Leaves failing criteria as `- [ ]`.
- Posts `## QA: PASS` or `## QA: FAIL` with full evidence.
- Does **not** close the issue and does **not** fix code.

### 3.4 Orchestrator (main session)
- The **only** agent that may close a GitHub Issue.
- **Before closing**, reads the issue body and confirms every AC checkbox is ticked `- [x]`. If any are still `- [ ]`, ticks them via `gh issue edit` before proceeding.
- Closes the issue only after all checkboxes are `- [x]` and an explicit `QA: PASS` comment exists.
- After closing, removes the worktree and deletes the feature branch (see §5).
- On `QA: FAIL`, routes back to the SWE subagent with the defect comment.
- On the third consecutive `QA: FAIL`, labels the issue `needs-human` and picks the next issue.

---

## 4. Automated Quality Gates

These checks run as pre-commit hooks and must all pass before any commit is accepted:

| Gate | Tool / command | Blocks on failure |
|---|---|---|
| Linting | `ruff check .` or `flake8` | Yes |
| Unit tests | `pytest tests/unit -q` | Yes |
| JSON Schema validation | `python scripts/validate_schemas.py` (validates all files in `config/` against `schemas/`) | Yes |
| Secret scan | Check that no `*.key.json`, `*.pem`, or `credentials*.json` is staged | Yes — hard block |

**Never skip hooks with `--no-verify`** unless the Orchestrator explicitly instructs it and states the reason in the commit message.

---

## 5. Parallel Execution via Git Worktrees

### 5.1 Creating a worktree

When the Orchestrator dispatches the SWE subagent to work on Issue #N:

```bash
git worktree add .worktrees/issue-N -b feature/issue-N
```

The SWE subagent works exclusively inside `.worktrees/issue-N/`. It does **not** touch the main worktree.

### 5.2 Credential isolation

- `GOOGLE_APPLICATION_CREDENTIALS` must point to the service-account key file **outside** the repository (e.g. `~/.config/m4-sales/sa.key.json`).
- Every worktree reads the key from the same external path. **Never copy the key file into a worktree directory.**
- Each worktree uses request IDs prefixed with the issue number: `issue-N-<uuid>` to prevent ledger row collisions when multiple worktrees run E2E tests simultaneously.

### 5.3 Sandbox Drive isolation for E2E

- Golden-set / E2E tests in parallel worktrees must write to **separate sandbox output folders** on the sandbox Shared Drive.
- Folder naming convention: `sandbox/issue-N/<job_id>/`.
- Jobs in different worktrees must never write to the same folder.

### 5.4 Removing a worktree (after issue is closed)

```bash
git worktree remove .worktrees/issue-N
git branch -d feature/issue-N
# Delete sandbox output folder on the Drive for issue N (manual or via a cleanup script)
```

Run cleanup **only after the issue is closed** and the PR is merged to `main`.

---

## 6. Loop Limits and Escalation

| Condition | Action |
|---|---|
| QA: FAIL (1st or 2nd time) | Orchestrator routes issue back to SWE with the QA comment. |
| QA: FAIL (3rd time) | Orchestrator adds label `needs-human`, posts a summary comment listing all three QA failures, and moves to the next issue. |
| Issue blocked on Q-xx or VERIFY | PM labels it `blocked: question`; Orchestrator skips it until a human removes the label. |
| SWE session exits unexpectedly | Orchestrator re-dispatches from the last successful step in the worktree. |

---

## 7. Issue Lifecycle Summary

```
[created] → needs-grooming → [groomed] → in-progress → [QA: PASS] → closed
                                                  ↑ (QA: FAIL, up to 3x)
                                             needs-human (3rd FAIL)
```

Labels used: `phase:P0`–`phase:P5`, `human`, `blocked: question`, `needs-grooming`, `in-progress`, `needs-human`, `backlog`.
