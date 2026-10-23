# Task Backlog: Template-Driven Document Assembly Engine

> Derived from `_docs/MVP_scope_plan.md` (SPEC-MVP-002 v0.2.0) and `_docs/architecture.md`.
> Tasks follow delivery phases P0–P5. Tasks marked **[HUMAN]** require a person and must never be assigned to coding subagents.
> Task #1 is the runnable skeleton — every subsequent task depends on it passing.

---

## 1. Barebones runnable repository with skill skeleton, `doctor` health check, and green test suite

**Goal:** Establish a clean, importable project skeleton that passes all automated checks with no live Google API calls.

**Description:** Create the directory layout from `_docs/architecture.md` §3, a minimal `SKILL.md`, stub Python scripts (`doctor.py`, `scan_template.py`, `validate_request.py`, `assemble.py`) with correct CLI argument parsing and exit-code contracts (§4), `requirements.txt` with pinned dependencies, and a `pytest` suite that runs the `doctor` against a fake workspace config and asserts exit 0. Advances AD-01, AD-02, SB-02, NF-04.

**Dependencies:** None

---

## 2. [HUMAN] P0 — Create Google Cloud project and service account

**Goal:** A service account key file exists, the Drive / Docs / Sheets APIs are enabled, and the key is shared with the team outside the repo.

**Description:** A person with Google Cloud Console access creates the service account, enables the required APIs, downloads the JSON key, and distributes it via a secure channel. This is a one-time human setup task. Advances AD-07, SB-01, SB-02, G-12.

**Dependencies:** None

---

## 3. [HUMAN] P0 — Provision Shared Drive and folder structure

**Goal:** The Shared Drive exists with `masters/`, `review/`, `approved/`, and `quarantine/` folders; the service account is granted the minimum necessary role.

**Description:** The Workspace Owner or Drive admin creates the Shared Drive, adds the four folders, and grants the service account membership (VERIFY: minimum role for file copy and move). Records Drive IDs in `config/workspace.yaml`. Advances AD-08, G-11, G-12.

**Dependencies:** Task #2

---

## 4. [HUMAN] P0 — Confirm Claude Team plan seats include Claude Code

**Goal:** Every teammate who will run jobs has a seat that includes Claude Code access.

**Description:** Review current Claude Team plan pricing and confirm which seat tier includes Claude Code CLI. Resolves open question Q-08 and CORR-04. Advances U-10, G-11.

**Dependencies:** None

---

## 5. `doctor.py` — Full health-check implementation

**Goal:** `doctor.py` verifies credentials, API reachability, Shared Drive membership, and master template accessibility, returning structured JSON.

**Description:** Implement all five checks from `_docs/architecture.md` §4.1 against real Google APIs (unit tests use fakes). The script reads `config/workspace.yaml` for Drive IDs and the master revision. Returns `{"status": "ok"|"degraded"|"fail", "checks": [...]}` on stdout and exits with the appropriate code. Advances G-11, G-12, SB-01, SB-04.

**Dependencies:** Task #1, Task #3

---

## 6. JSON Schema definitions for all five contracts

**Goal:** All five JSON Schema files in `schemas/` are valid Draft 2020-12 schemas that match the scope plan entities (§4.2, §6.2–§6.4).

**Description:** Create `request.schema.json`, `recipe.schema.json`, `registry.schema.json`, `job.schema.json`, `event.schema.json` with required fields, types, enums, and pattern constraints. Contract tests in `tests/contract/` validate every schema with `jsonschema`. Advances AD-06, NF-04, G-02.

**Dependencies:** Task #1

---

## 7. [HUMAN] P1 — Decompose pilot contract family into master template

**Goal:** One master template exists in the `masters/` folder with every optional section wrapped in correctly balanced block markers.

**Description:** The Content Curator (R-03) manually decomposes the pilot contract family (resolving Q-01) into a single master Google Doc with `{{BEGIN:block_id}}` / `{{END:block_id}}` markers. `scan_template.py` must report 0 issues. Advances AD-03, AD-05, AD-14, G-01.

**Dependencies:** Task #3, Task #8

---

## 8. `scan_template.py` — Marker scan implementation

**Goal:** `scan_template.py` reads a Google Doc and reports all marker issues as structured JSON, exiting 1 if any issues are found.

**Description:** Implement full marker detection: unregistered, missing from registry, duplicate IDs, unbalanced, and nested markers. Reads the Docs API `document.body.content` element list. Unit tests use a fake Docs client with hand-crafted element lists covering all boundary conditions. Advances G-01, AD-05.

**Dependencies:** Task #1, Task #6

---

## 9. Block registry JSON for pilot family

**Goal:** `config/registry/<family_key>.json` validates against `registry.schema.json` and every block in it has a matching marker in the master template.

**Description:** After Task #7 completes, the Workflow Designer (R-04) authors the registry JSON, assigns block IDs, labels, kinds, and statuses. Re-run `scan_template.py` to confirm 0 issues. Advances AD-05, G-01, AD-06.

**Dependencies:** Task #7, Task #8, Task #6

---

## 10. [HUMAN] P2 — Author assembly recipe for pilot family

**Goal:** `config/recipes/<family_key>_v1.json` validates against `recipe.schema.json` and covers every option combination for the pilot family.

**Description:** The Workflow Designer authors the declarative recipe, mapping every customer option to block include/exclude lists. Resolves Q-02 (structured request vs free-text). Must pass `validate_request.py` against the golden-set request profiles. Advances AD-06, G-02.

**Dependencies:** Task #9, Task #6

---

## 11. `validate_request.py` — Request validation implementation

**Goal:** `validate_request.py` validates a request JSON against the recipe schema, returns structured errors, and exits 1 on invalid input.

**Description:** Implement all validation checks: schema conformance, option presence and allowed values, required placeholders present. Raises `UnknownOptionError` and `MissingPlaceholderError` with codes from §6.2. Unit tests cover 0-option, all-valid, unknown-option, missing-placeholder boundary cases. Advances AD-06, G-02, G-03.

**Dependencies:** Task #1, Task #6

---

## 12. Ledger adapter — Google Sheets implementation

**Goal:** The `LedgerAdapter` interface is fully implemented against Google Sheets, with all methods tested using a fake Sheets client.

**Description:** Implement `SheetsLedgerAdapter` satisfying the interface from `_docs/architecture.md` §6. Covers `create_job`, `update_job`, `get_job`, `find_job_by_request_id` (idempotency), `append_event`, `list_events`. All records include `workspace_id`. Optimistic-lock retry on job status updates (TL-09). Advances AD-12, AD-13, G-09, G-13.

**Dependencies:** Task #1, Task #6

---

## 13. `assemble.py` — Copy master and prune blocks

**Goal:** `assemble.py --dry-run` resolves the block list and reports it without writing to Drive; the full run copies the master and deletes unwanted block ranges.

**Description:** Implement the `copy_master` and `prune_blocks` steps. Block deletion uses `deleteContentRange` in descending index order (TL-01). Records `master_revision_id` at copy time and fails with `MasterRevisionMismatchError` if the live revision differs. Unit tests use a fake Drive + Docs client. Advances AD-03, G-04, G-05, G-08, TL-01.

**Dependencies:** Task #1, Task #11, Task #12, Task #6

---

## 14. `assemble.py` — Fill placeholders, strip markers, verify output

**Goal:** After pruning, all `{{PLACEHOLDER_KEY}}` strings are replaced and all block markers are stripped; the script verifies zero leftovers.

**Description:** Implement `fill_placeholders` (Docs `replaceAllText`), `strip_markers` (regex delete of any remaining `{{BEGIN:*}}` / `{{END:*}}`), and `verify_output` (re-reads the document and asserts 0 markers, 0 unresolved placeholders). Raises `MissingPlaceholderError` or `MarkerError` on failure. Advances G-06, AD-03.

**Dependencies:** Task #13

---

## 15. `assemble.py` — Review submission and failure safety

**Goal:** On success the output document is in the `review/` folder with a ledger record at `pending_review`; on any failure the partial output is quarantined and the job is marked `failed`.

**Description:** Implement `submit_for_review` (Drive file move) and the failure path (move to `quarantine/` or delete; update ledger). Post all step transitions as events to the ledger. Exponential backoff on transient API errors (NF-06). Advances G-07, G-09, G-10, G-13, AD-10, AD-12.

**Dependencies:** Task #14, Task #12

---

## 16. E2E golden-set tests on sandbox Shared Drive

**Goal:** All 10+ golden-set request profiles pass G-04, G-05, G-06, G-07, G-08, G-09, G-10 on the sandbox Shared Drive.

**Description:** Create golden-set request JSON files in `tests/golden/` covering every option at least once. Run `assemble.py` against the sandbox Drive, inspect the produced documents and ledger, and assert all acceptance criteria. Never use production data (SB-05). Advances G-04, G-05, G-06, G-08, G-09, G-10, G-11.

**Dependencies:** Task #15, Task #10

---

## 17. [HUMAN] P4 — Second teammate onboarding test

**Goal:** A teammate clones the repo, configures credentials, runs `doctor.py`, and executes a golden-set job successfully with no code changes.

**Description:** Follow the README setup steps on a clean machine. Confirms G-11 (team portability). Record any friction points and open issues for fixes. Advances G-11, AD-09.

**Dependencies:** Task #16, Task #4

---

## 18. Access boundary verification

**Goal:** The service account cannot access files outside the designated Shared Drive; a secret scan finds no credentials in the repo.

**Description:** Run a denied-access test (attempt to read a file the service account was not granted access to; assert 403). Run `git log --all -- '*.json' '*.key*' '*.pem'` and a secret-scanning tool to confirm no credentials were ever committed. Advances G-12, SB-01, SB-02.

**Dependencies:** Task #5

---

## 19. [HUMAN] P5 — Pilot measurement: manual vs automated time

**Goal:** Over ≥ 5 real pilot contracts, hands-on time per contract is recorded and compared with the manual baseline.

**Description:** Team records time for each contract assembly using the tool vs the previous manual process. Reports ≥ 50% reduction target (G-14, ASSUMED). Results inform whether to expand to further document families.

**Dependencies:** Task #17

---

## 20. `review` script — Approve / reject workflow

**Goal:** A reviewer can call the review script to approve or reject a job, moving the output to `approved/` and recording a `ReviewDecision` in the ledger.

**Description:** Implement `review.py` with `--job-id` and `--decision approved|rejected [--reason "..."]`. Moves the Drive file, appends a `ReviewDecision` record, and updates job status to `approved` or `rejected`. Validates that the caller is an R-06 identity (VERIFY: how identity is confirmed in the CLI context). Advances G-07, AD-10.

**Dependencies:** Task #15, Task #12
