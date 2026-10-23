# Architecture Specification: Template-Driven Document Assembly Engine

> **Spec:** `SPEC-MVP-002` v0.2.0 · **Status:** Draft
> Drawn from `_docs/MVP_scope_plan.md`. Every component maps to scope plan IDs. VERIFY items must be re-checked against current vendor docs before implementation.

---

## 1. Architecture Overview

The system has **four layers** with explicit file/API contracts between them. No layer reaches across another's boundary.

```
┌─────────────────────────────────────────────────────────────────┐
│  INTERFACE LAYER                                                │
│  SKILL.md  ·  Claude Code orchestration session               │
│  (interprets request, resolves ambiguity, calls scripts)       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ subprocess + stdin JSON / stdout JSON
┌───────────────────────────▼─────────────────────────────────────┐
│  SERVICE LAYER (Python scripts)                                 │
│  scan_template · validate_request · assemble · review          │
│  Each script is a CLI with a defined contract (§4)             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Google API client + GOOGLE_APPLICATION_CREDENTIALS
┌───────────────────────────▼─────────────────────────────────────┐
│  DATA LAYER                                                     │
│  Ledger adapter (Google Sheets) · Drive/Docs API               │
│  Storage-agnostic repository interface (§6)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Shared Drive + service account (AD-07, AD-08)
┌───────────────────────────▼─────────────────────────────────────┐
│  STORAGE (Google Drive)                                         │
│  masters/  ·  review/  ·  approved/  ·  quarantine/           │
│  ledger.sheets (jobs tab + events tab)                         │
└─────────────────────────────────────────────────────────────────┘
```

**Key decisions respected (AD-01–AD-14):**
- Claude Code is orchestration only; Python scripts do all document mutation (AD-01).
- No server, web UI, or daemon (AD-02).
- Assembly is subtractive: copy master → delete unwanted blocks → fill placeholders → strip markers (AD-03).
- Additive assembly (cross-doc block copy) is deferred (AD-04).
- One master per document family; decomposition is a one-time governed phase (AD-05).
- Recipes are declarative JSON files; unknown options hard-fail (AD-06).
- Service account, not individual identity (AD-07).
- Shared Drive, not personal My Drive (AD-08 — VERIFY: check org Workspace edition).
- Git distribution; no secrets committed (AD-09).
- Mandatory human approval gate; engine never sends documents (AD-10).
- Masters are immutable to jobs; only Curators may edit them (AD-11).
- Google Sheet ledger, workspace-ready schema (AD-12, AD-13).
- Single document family pilot (AD-14).

---

## 2. Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Stable Google API client support; matches team familiarity (ASSUMED) |
| Google API clients | `google-api-python-client` + `google-auth` | Official; service-account credential flow built in |
| Schema validation | `jsonschema` (Draft 2020-12) | Lightweight; validates request, recipe, block registry, job record, event |
| Test framework | `pytest` + `pytest-parametrize` | Parameterised boundary coverage; standard |
| Fakes / mocks | `unittest.mock` + hand-rolled Google API fakes | Unit tests never call live APIs |
| Dependency pinning | `requirements.txt` with pinned versions; `pip-compile` optional | Reproducibility |
| Packaging | Scripts live in `.claude/skills/document-assembly/scripts/`; no pip package | Matches AD-02 — no standalone app |
| Container | Not adopted in MVP | No daemon, no server; unjustified complexity (AD-02) |

**VERIFY before coding:**
- Confirm `google-api-python-client` version that supports Shared Drive `supportsAllDrives` on all relevant endpoints (VERIFY, AD-08).
- Confirm which OAuth scopes are the minimum for each operation (VERIFY, SB-04).

---

## 3. Repository Layout

```
.
├── .claude/
│   └── skills/
│       └── document-assembly/
│           ├── SKILL.md                  # Skill entry point (Claude reads this)
│           └── scripts/
│               ├── doctor.py             # Health check — verifies credentials, API, Drive, master
│               ├── scan_template.py      # Decomposition helper: validates markers in a master
│               ├── validate_request.py   # Validates a request JSON against recipe schema
│               └── assemble.py           # Core job runner: copy → prune → fill → verify → submit
├── config/
│   ├── workspace.yaml                    # Workspace config: drive IDs, folder IDs, ledger ref
│   ├── registry/
│   │   └── <family_key>.json            # ContentBlock registry per family
│   └── recipes/
│       └── <family_key>_v<N>.json       # AssemblyRecipe per family + version
├── tests/
│   ├── unit/                             # Pytest unit tests; fakes only, no live API
│   ├── integration/                      # Modules wired together; fake Google clients
│   ├── contract/                         # CLI JSON output + exit codes vs JSON Schemas
│   └── golden/                           # E2E golden-set requests; run on sandbox Shared Drive
├── schemas/
│   ├── request.schema.json
│   ├── recipe.schema.json
│   ├── registry.schema.json
│   ├── job.schema.json
│   └── event.schema.json
├── _docs/
│   ├── MVP_scope_plan.md
│   ├── architecture.md                   # This file
│   ├── tasks.md
│   ├── task-template.md
│   ├── process.md
│   └── team/
│       ├── pm.md
│       ├── software-engineer.md
│       └── qa-engineer.md
├── AGENTS.md
├── CLAUDE.md                             # Single line: @AGENTS.md
├── .gitignore                            # Excludes credentials/, *.key.json, .venv/, etc. (SB-02)
└── README.md
```

---

## 4. Script CLI Contracts

Every script writes **only to stdout** (JSON) and **stderr** (human-readable diagnostics). Exit codes are uniform:

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Validation / logic error (non-retryable) |
| 2 | External / transient error (retryable) |
| 3 | Credential / permission error (human action required) |

### 4.1 `doctor.py`

```
python scripts/doctor.py [--workspace config/workspace.yaml]
```

**Checks (all against fakes in unit tests; live in integration/E2E):**
1. `GOOGLE_APPLICATION_CREDENTIALS` env var is set and file exists.
2. Service account can authenticate (token fetch).
3. Drive API reachable; service account is a member of the configured Shared Drive (VERIFY: `drives.get` permission model).
4. Master template file ID is readable and its revision ID matches `workspace.yaml`.
5. Ledger sheet is readable.

**Stdout (JSON):**
```json
{"status": "ok"|"degraded"|"fail", "checks": [{"name": "...", "status": "pass"|"fail", "detail": "..."}]}
```

### 4.2 `scan_template.py`

```
python scripts/scan_template.py --file-id <DRIVE_FILE_ID> [--registry config/registry/<family>.json]
```

**Stdout:**
```json
{
  "file_id": "...",
  "markers_found": [{"block_id": "...", "start_index": 0, "end_index": 0}],
  "issues": {
    "unregistered_markers": [],
    "registry_without_marker": [],
    "duplicate_ids": [],
    "unbalanced_markers": [],
    "nested_markers": []
  },
  "summary": {"total_markers": 0, "issue_count": 0}
}
```

Exit 1 if `issue_count > 0`.

### 4.3 `validate_request.py`

```
python scripts/validate_request.py --request <request.json> --recipe config/recipes/<family>_v<N>.json
```

**Stdout:**
```json
{"valid": true|false, "errors": [{"field": "...", "code": "...", "message": "..."}]}
```

### 4.4 `assemble.py`

```
python scripts/assemble.py --request <request.json> [--dry-run] [--workspace config/workspace.yaml]
```

`--dry-run` resolves blocks and validates without writing to Drive.

**Stdout (streaming newline-delimited JSON events during run; final summary last):**
```json
{"event": "step_started"|"step_succeeded"|"step_failed"|"job_completed"|"job_failed", "step": "...", "job_id": "...", "detail": {}}
```

**Error codes** (§6.2 of scope plan):

| Code | Exception class | Trigger |
|---|---|---|
| `unknown_option` | `UnknownOptionError` | Request option not in recipe |
| `missing_placeholder` | `MissingPlaceholderError` | Required placeholder value absent |
| `marker_error` | `MarkerError` | Unbalanced, nested or duplicate markers in master |
| `master_revision_mismatch` | `MasterRevisionMismatchError` | Live master revision ≠ approved revision |
| `recipe_conflict` | `RecipeConflictError` | A block is both included and excluded by recipe rules |
| `api_error` | `GoogleApiError` | Transient or permanent Google API failure |

---

## 5. JSON Schema Contracts

All schemas live in `schemas/`. Scripts and tests validate against them with `jsonschema`.

### 5.1 Request (`request.schema.json`)

```json
{
  "request_id": "string (idempotency key)",
  "family_key": "string",
  "options": {"<option_key>": "<value>"},
  "placeholder_values": {"<PLACEHOLDER_KEY>": "<value>"},
  "requested_by": "string (email / identity)"
}
```

### 5.2 Recipe (`recipe.schema.json`)

```json
{
  "family_key": "string",
  "version": "integer",
  "options": [{"option_key": "string", "allowed_values": ["..."], "required": true}],
  "rules": [{"when": {"<option_key>": "<value>"}, "include": ["block_id"], "exclude": ["block_id"]}],
  "defaults": {"include": ["block_id"]},
  "placeholder_map": {"<PLACEHOLDER_KEY>": "<request_field>"},
  "status": "draft|published|retired"
}
```

### 5.3 Block Registry (`registry.schema.json`)

```json
{
  "family_key": "string",
  "blocks": [{
    "block_id": "string (^[a-z0-9_]{3,64}$)",
    "label": "string",
    "kind": "section|clause|table|annex",
    "optional": "boolean",
    "source_ref": "string",
    "owner": "string",
    "status": "proposed|active|deprecated|removed"
  }]
}
```

### 5.4 Job Record (`job.schema.json`)

Matches `AssemblyJob` entity from scope plan §4.2.

### 5.5 Event (`event.schema.json`)

```json
{
  "event_id": "string",
  "job_id": "string",
  "workspace_id": "string",
  "event_type": "string",
  "occurred_at": "ISO 8601 timestamp",
  "actor": "string",
  "detail": {}
}
```

---

## 6. Data Isolation Layer (Ledger Adapter)

The ledger adapter is a **storage-agnostic repository interface**. MVP implementation uses Google Sheets; the interface can be swapped for a database (AD-12) without changing script logic.

### Interface (Python abstract base)

```python
class LedgerAdapter:
    def create_job(self, job: dict) -> str: ...          # returns job_id
    def update_job(self, job_id: str, patch: dict): ...
    def get_job(self, job_id: str) -> dict: ...
    def find_job_by_request_id(self, request_id: str, workspace_id: str) -> dict | None: ...
    def append_event(self, event: dict): ...
    def list_events(self, job_id: str) -> list[dict]: ...
```

### Rules

- Every record carries `workspace_id` (immutable after creation) — AD-13.
- Events are append-only; no update or delete on the events tab.
- `request_id` is unique per workspace; `find_job_by_request_id` implements idempotency for G-09.
- Concurrency: use Google Sheets row-append (not read-modify-write) for events. For job status updates, read the row first and check `updated_at` matches before writing (optimistic lock). If mismatch, retry up to TL-09 limit — VERIFY exact Sheets API behaviour.
- Schema version stored in a metadata row/tab; migration path: add columns, never remove or rename.

---

## 7. Google API Usage

| Module | API | Operations | OAuth scope | Justification |
|---|---|---|---|---|
| `doctor` | Drive v3 | `drives.get`, `files.get` | `drive.readonly` | Verify membership and master reachability |
| `scan_template` | Docs v1 | `documents.get` | `documents.readonly` | Read document structure for marker scan |
| `assemble` — copy master | Drive v3 | `files.copy` | `drive.file` | Copy master to review folder (AD-03) |
| `assemble` — prune blocks | Docs v1 | `documents.batchUpdate` (deleteContentRange) | `documents` | Delete unwanted block ranges |
| `assemble` — fill placeholders | Docs v1 | `documents.batchUpdate` (replaceAllText) | `documents` | Substitute placeholder values |
| `assemble` — move to quarantine | Drive v3 | `files.update` (parents) | `drive.file` | On failure, move partial output (G-10) |
| `review` — approve | Drive v3 | `files.update` (parents) | `drive.file` | Move approved doc to approved folder (G-07) |
| `ledger` | Sheets v4 | `spreadsheets.values.append`, `get`, `update` | `spreadsheets` | Job records and event log (AD-12) |

**SB-04 rule:** request only the scopes listed. No `drive` (full) scope unless a specific operation requires it. VERIFY each scope against current Google documentation.

**Delete order (TL-01):** when deleting multiple block ranges in one `batchUpdate`, sort ranges by `startIndex` descending so earlier deletions don't shift the indices of later ones.

---

## 8. Runtime and Observability

### 8.1 Environment

```bash
# Setup (once per machine / per teammate)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.key.json
# Key file lives OUTSIDE the repo. Never inside. (SB-02)
```

### 8.2 `doctor` health check

Run before any job submission:
```bash
python .claude/skills/document-assembly/scripts/doctor.py
```
Expected: `{"status": "ok", ...}`. On `degraded` or `fail`, fix before proceeding.

### 8.3 Structured logging

- All scripts log to **stderr** as newline-delimited JSON: `{"level": "INFO|WARN|ERROR", "job_id": "...", "request_id": "...", "step": "...", "message": "..."}`.
- `job_id` and `request_id` are included on every log line once known.
- **Never log document content, placeholder values, or any PII** (SB-06).
- Stdout is reserved for machine-readable JSON output only.

### 8.4 Retry policy

Transient Google API errors (HTTP 429, 500, 503): exponential backoff, base 1 s, max 5 retries (NF-06). Non-retryable errors (400, 403, 404) surface immediately with the appropriate error code.

---

## 9. Testing Strategy

| Tier | Scope | Google API | Location |
|---|---|---|---|
| Unit | Individual functions / classes | Hand-rolled fakes (never real) | `tests/unit/` |
| Integration | Scripts wired together | Fake Google clients injected via DI | `tests/integration/` |
| Contract | Script CLI: JSON output, exit codes, error codes | Fake | `tests/contract/` — validates against `schemas/` |
| E2E / Golden | Full run on sandbox Shared Drive | Real API, sandbox Drive only | `tests/golden/` — never production data (SB-05) |

**Boundary values for parameterised tests (NF-04):**
- Block counts: 0, 1, 2, typical (10), max (60), max+1 (61 — should fail).
- Placeholder counts per block: 0, 1, typical, max (100), max+1.
- Marker edge cases: unbalanced, nested, duplicate IDs, zero-length range.

---

## 10. Traceability

| Component | Scope plan IDs satisfied |
|---|---|
| `doctor.py` | G-11, G-12, SB-01, SB-04 |
| `scan_template.py` | G-01, AD-05 |
| `validate_request.py` | G-02, AD-06 |
| `assemble.py` — copy step | G-03, G-04, G-08, AD-03, AD-11 |
| `assemble.py` — prune step | G-05, G-06, TL-01 |
| `assemble.py` — fill + strip | G-06, AD-03 |
| `assemble.py` — verify step | G-04, G-06 |
| `assemble.py` — submit for review | G-07, AD-10 |
| `assemble.py` — failure path | G-10 |
| Ledger adapter | G-09, G-13, AD-12, AD-13 |
| JSON Schemas | G-02, NF-04, AD-06 |
| `.gitignore` + credential rules | G-12, SB-02 |
| `config/workspace.yaml` | AD-08, AD-13 |
| Golden-set tests | G-04, G-05, G-06, G-07, G-08, G-09, G-10, G-11 |

**VERIFY items to re-check before each component is built:**
- AD-08: confirm Shared Drive availability in the org's Workspace edition.
- AD-07 / SB-04: confirm minimum Drive + Docs + Sheets scopes for service account.
- TL-09: confirm Sheets API concurrency / quota limits for concurrent job writes.
- CORR-04: confirm Claude Team plan seat types and Claude Code inclusion.
