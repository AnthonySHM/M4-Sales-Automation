# MVP Scope Specification: Template-Driven Document Assembly Engine

> **Pilot application:** automated assembly of customer contracts from nested Google Drive templates, run by a team through a shared Claude Code skill.
> **Generalised form:** a decoupled, workspace-scoped engine that assembles formatted documents from a governed library of content blocks according to declarative rules, with tracked job state, access controls, status events and a mandatory human approval gate.

---

## 1. Document Metadata & Requirement Provenance

### 1.1 Metadata

| Field | Value |
|---|---|
| Document ID | `SPEC-MVP-002` |
| Version | 0.2.0 |
| Status | Draft. Analyst defaults await stakeholder confirmation (see §1.6) |
| Created / updated | 2026-10-22 |
| Author | Systems analysis pass (Claude), from the requester's design conversation |
| Requester | Anthony Shiloo |
| Location | `_docs/MVP_scope_plan.md` |
| Supersedes | `SPEC-MVP-001` v0.1.0 (generic engine spec, kept as `_docs/MVP_scope_plan.v0.1.0-generic.md`) |
| Audience | Downstream design, build, test and review agents, plus the human team that will run the system |

### 1.2 How to read provenance

Every decision carries an **origin** tag so downstream agents know how hard to push back:

| Tag | Meaning | How to treat it |
|---|---|---|
| `USER` | Stated directly by the requester in the design conversation | Hold firm. Change only with requester sign-off |
| `AGREED` | Proposed by the analyst; the requester explicitly accepted it | Hold unless new evidence contradicts it |
| `INFERRED` | Strong reading of user signals; not explicitly confirmed | Confirm with requester before costly work depends on it |
| `ASSUMED` | Analyst default, chosen for lack of input | Challenge freely |
| `CORRECTED` | Supersedes something said earlier in the conversation that was inaccurate or overstated | Do not resurrect the earlier claim |
| `VERIFY` | Depends on a third-party product fact (Google, Anthropic) that may have changed | Re-check against current vendor docs before relying on it |

### 1.3 Source signals

**Commissioning brief (verbatim):**
> "Build a decoupled, multi-tenant automated workflow processing engine with real-time event distribution, user access controls, persistent state tracking, and automated task dispatching." The requester added: *"I want the plan to be based on the project we discussed on this chat."*

**User signals from the design conversation:**

| ID | Signal (paraphrased from the requester) | Interpreted requirement |
|---|---|---|
| U-01 | Colleagues edit documents in **Google Drive** | Source and output documents live in Google Drive; the engine operates on them in place via API |
| U-02 | They are "tired of the constant rework… the repetition of editing this document every time" | Primary value is eliminating repetitive manual assembly |
| U-03 | Documents are **templates**, with sections and tables "taken from other templates", i.e. "templates of templates" | Source content is **nested**; there is no clean block library today |
| U-04 | Which pieces are used "depends on the customer" | Assembly is **conditional** on per-request options |
| U-05 | Heavy formatting and layout "need to be preserved because they are contracts" | **Formatting fidelity is a hard requirement**; output carries legal weight |
| U-06 | "I want other people to also use this project" | Multi-user team use; shared tooling |
| U-07 | Concern that teammates would be "using my email" for Drive access | Access must not depend on one person's personal identity |
| U-08 | Prefers not to build a standalone Python application; accepts Python scripts living inside a Claude skill | Packaging: scripts bundled in a skill, invoked by Claude Code |
| U-09 | Will build in a local folder with Claude Code; team shares it | Local Claude Code project, distributed through a shared repository |
| U-10 | Is on (or evaluating) the Claude **Team plan** | Team plan is the collaboration and seat layer |
| U-11 | Wants a step-by-step workflow for "automating one contract" first | MVP is a **single document family, single-job** pilot before scaling |

**Brief signals (from the commissioning prompt):**

| ID | Signal |
|---|---|
| R-01 | Roles and entities must stay domain-agnostic |
| R-02 | Goals must be checkable (pass/fail) |
| R-03 | Provenance must let downstream agents challenge stale assumptions |
| R-04 | Cover entities, schemas and lifecycle transitions |
| R-05 | Record non-functional bounds, security boundaries and technical limits |

**Mapping of brief keywords to this project:**

| Brief keyword | Meaning in this project | MVP treatment |
|---|---|---|
| "decoupled" | Judgment (Claude), deterministic document operations (scripts), state (ledger), content (Drive) and review (humans) are separate components with file/API contracts between them | **In scope** |
| "multi-tenant" | Tenant = **Workspace** (one organisation or team: its Drive area, repo, credentials and recipes) | **Single workspace in MVP.** All records carry `workspace_id` so a second workspace needs no schema change |
| "real-time event distribution" | Job status changes become visible to the team as they happen | **Near-real-time**: append-only event log in a shared ledger the team can watch. Push notifications deferred |
| "user access controls" | Who can run jobs, edit the library and recipes, approve output, and hold the service credential | **In scope**, using Drive sharing roles, repo access, Team plan membership and a service identity |
| "persistent state tracking" | Every assembly job and its transitions are durably recorded | **In scope** (shared job ledger plus Drive revision history) |
| "automated task dispatching" | Once a job is requested, its steps run without manual intervention up to the review gate | **In scope within a job.** A queue that dispatches jobs without a person triggering them is deferred |

### 1.4 Architectural decisions

| ID | Decision | Origin | Derived from | Rationale | Revisit if… |
|---|---|---|---|---|---|
| AD-01 | **Two-layer execution.** Claude Code, via a skill, handles interpretation and orchestration: reading the request, resolving ambiguity with the user, choosing the recipe and calling scripts. **Python scripts** bundled in the skill perform every document mutation deterministically. Claude never retypes or regenerates contract content. | AGREED | U-05, U-08 | Gets AI flexibility for variable requests and exact, repeatable document edits | Requests become fully structured (a form), which would make the AI layer optional |
| AD-02 | **No standalone application.** Scripts live in the skill folder (`.claude/skills/<skill>/scripts/`) and are invoked by Claude Code. There is no server, web UI or daemon in MVP. | AGREED | U-08 | Lowest operational burden; matches the requester's preference | Volume needs unattended or scheduled batch runs (see Q-03) |
| AD-03 | **Subtractive assembly from a master template.** For each document family, one **master template** contains *every* optional block, each wrapped in explicit block markers. A job (1) copies the master with the Drive file-copy operation, which preserves all formatting, (2) deletes the blocks not selected, (3) fills placeholders, and (4) strips the markers. | ASSUMED | U-03, U-05 | Copying a whole file preserves formatting exactly. Deleting ranges is far safer than rebuilding formatted content in another document (see CORR-02) | One master per family becomes unmanageable (block count or variants explode), or a block must appear in several positions |
| AD-04 | **Additive assembly is out of MVP.** Copying a formatted block *from one document into another* is a deferred capability. If it's later needed, evaluate a `.docx` round-trip (export, merge with a library such as python-docx, re-import) against element-by-element Docs API reconstruction. | ASSUMED | CORR-02 | Neither path is trivial; both need a fidelity spike before commitment | The master-template model (AD-03) fails G-04 |
| AD-05 | **Decomposition is a governed, one-time phase.** Existing nested templates are untangled into master templates plus a **block registry** (a machine-readable list of every block, its marker, conditions and owner) before any automation runs. | AGREED | U-03; requester: "the real work would be disassembling… into an organized structure" | Automation is only as reliable as explicit block boundaries; this moves tacit knowledge out of people's heads | — |
| AD-06 | **Selection rules are declarative.** An **assembly recipe** file per family maps request options to block IDs and placeholder values. Claude may *propose* a recipe interpretation for an unusual request, but only blocks resolved through the recipe are applied. Unknown options fail the job. | ASSUMED | U-04, U-05 | Contracts need deterministic, reviewable selection logic, not ad-hoc AI judgment | The team needs free-form drafting beyond the block library |
| AD-07 | **Service identity for Google access.** A Google Cloud service account, owned at organisation level and not tied to any individual, holds Drive/Docs access. Teammates' runs authenticate as it. | AGREED | U-07 | Removes the single point of failure of one person's account | Per-person edit attribution becomes a requirement. Alternative: per-user OAuth, where each teammate's own Google identity performs edits |
| AD-08 | **Work happens on a Shared Drive.** Master templates, output and the job ledger live on a Shared Drive where the service account is a member with the minimum role needed. | ASSUMED + VERIFY | AD-07, TL-06 | Service accounts generally lack personal Drive storage, so files they create in someone's My Drive can fail or have awkward ownership. A Shared Drive avoids both problems | The organisation can't use Shared Drives (check the Google Workspace edition) |
| AD-09 | **Distribution through a shared git repository.** The skill, scripts, registry, recipes and tests are committed to one repo; each teammate clones it and runs Claude Code in that folder. Secrets are never committed. | AGREED | U-06, U-09 | Single source of truth; versioned changes to rules and code | The organisation prefers org-provisioned skills through Claude settings. Evaluate in parallel, since scripts still need a runtime with Google credentials |
| AD-10 | **Mandatory human approval gate.** Every output starts as a draft awaiting review. Only a Reviewer can mark it approved, which moves it to the approved location. The engine never sends documents to third parties. | AGREED | U-05 | Contracts carry legal weight; automation assembles but people approve | Never removed. It may be streamlined, but not removed |
| AD-11 | **Originals are immutable to jobs.** Jobs only ever *copy* masters. Writes to master templates happen only through the curation flow (Content Curator role). Each job records the master's revision ID that it copied. | AGREED | Discussion: "your originals untouched" | Reproducibility and safety | — |
| AD-12 | **Shared job ledger as state store and event source.** Job records and an append-only transition and event log live in a shared, team-readable store (default: a Google Sheet on the Shared Drive with `jobs` and `events` tabs). | ASSUMED | Brief: persistent state, event distribution; U-06 | Every teammate's local clone writes to one shared place. Observers can watch it with no extra infrastructure | Concurrent writes conflict, or volume outgrows a spreadsheet. Then move to a database |
| AD-13 | **Single workspace, workspace-ready schema.** MVP serves one organisation; every config and record still carries `workspace_id`. | ASSUMED | Brief "multi-tenant" vs U-11 | Avoids premature multi-tenancy while keeping the door open | A second team or organisation needs to run it |
| AD-14 | **Pilot scope: one document family.** Build, test and approve end-to-end for one contract family before adding others. | INFERRED | U-11 | De-risks the decomposition approach on real material | — |

### 1.5 Decision history and corrections

| Version | Date | Change | Driver |
|---|---|---|---|
| 0.1.0 | 2026-10-22 | Generic multi-tenant workflow engine spec produced from the brief alone, with no project context | Brief only |
| 0.2.0 | 2026-10-22 | Rewritten around the requester's document-assembly project. Generic engine concepts mapped to project concepts (§1.3); scope reduced to single workspace and near-real-time events; subtractive assembly adopted | Requester: "based on the project we discussed" |

**Corrections to claims made earlier in the design conversation.** Downstream agents should not rely on the original claims:

| ID | Earlier claim | Correction | Origin |
|---|---|---|---|
| CORR-01 | "Claude Code can record what worked and commit it as a skill automatically" for the document-editing workflow | That automatic recording applies to specific bundled skills for running and verifying apps. A document-assembly skill has to be **authored**, though the skill-creator skill and Claude Code can draft it | CORRECTED |
| CORR-02 | "The Google Docs API preserves formatting well… insert this table here, this clause there" | Precise edits and deletions inside one document are reliable. **Copying a formatted section from one Google Doc into another** has no single API operation: text, paragraph styles, lists and tables must be rebuilt element by element, which is error-prone for complex contracts. That's why AD-03 makes assembly subtractive | CORRECTED |
| CORR-03 | "Three Python scripts" are needed | That number was illustrative. Script count follows the job's functions, not a per-skill rule. §6.2 defines the MVP script set | CORRECTED |
| CORR-04 | Team plan pricing and minimums quoted in conversation (Standard ≈ $25/seat monthly or $20 annual; Premium ≈ $125/$100; minimum of 2 seats) | Sources disagreed on the minimum (2 vs 5 seats) and on which seat types include Claude Code. Confirm current terms before purchasing seats | VERIFY |
| CORR-05 | "The person who created the Google Drive space creates the service account" | Two separate roles. Someone with Google Cloud Console access creates the service account. The **owner or manager of the Drive location** grants it access. They may or may not be the same person | CORRECTED |

### 1.6 Open questions

| ID | Question | Blocks |
|---|---|---|
| Q-01 | Which contract family is the pilot, and how many optional blocks and placeholders does it have? | AD-14, G-01, NF-02 |
| Q-02 | How are customer options captured today: email, form, call notes? Should MVP accept free text that Claude converts into a structured request, or a filled form only? | AD-06, §6.3 |
| Q-03 | Contracts assembled per week (asked in conversation, not yet answered) | AD-02, NF-01 |
| Q-04 | Must every edit be attributable to the individual teammate (audit or legal), which would favour per-user OAuth over a service account? | AD-07 |
| Q-05 | Does the organisation use Google Workspace with Shared Drives available? Who administers it? | AD-08, R-01 |
| Q-06 | Who are the authorised Reviewers, and does approval need to be recorded with a specific identity or signature? | AD-10, G-07 |
| Q-07 | Do blocks ever appear in headers, footers or footnotes, or only in the document body? | TL-03 |
| Q-08 | Do Team plan seats for all users include Claude Code, or are Premium seats required? | U-10, CORR-04 |
| Q-09 | Is Google Docs the required output format, or is a Word or PDF export also needed at approval time? | §6.5 |

---

## 2. Domain-Agnostic User Roles

Roles describe **function**, not job title. One person may hold several roles; the pilot mapping is shown for orientation only.

| ID | Role | Scope | Responsibilities | Pilot example |
|---|---|---|---|---|
| R-01 | **System Administrator** | Platform | Creates and rotates the service identity; manages cloud project, API enablement and Claude organisation settings; grants and revokes access | Google Workspace or Cloud admin; Claude Team owner |
| R-02 | **Workspace Owner** | One workspace | Owns the Shared Drive, repo and ledger; assigns roles; approves changes to recipes and registry | Team lead |
| R-03 | **Content Curator** | One workspace, library | Decomposes source templates into master templates; maintains block markers and the block registry; the only role allowed to edit masters | Senior contract editor |
| R-04 | **Workflow Designer** | One workspace, rules and code | Authors recipes, the skill (`SKILL.md`) and scripts; maintains tests | Technical team member using Claude Code |
| R-05 | **Job Requester (Operator)** | One workspace | Submits an assembly request; runs, retries or cancels their own jobs; fixes rejected requests | Any team member preparing a contract |
| R-06 | **Reviewer (Approver)** | One workspace | Inspects draft output; approves or rejects with a reason. Cannot approve a job they requested if separation of duties is enabled | Authorised signatory or legal reviewer |
| R-07 | **Task Executor** (non-human) | One workspace, granted folders only | Performs the automated steps of a job: Claude Code running the skill, plus the scripts acting as the service identity | Claude Code + service account |
| R-08 | **Event Observer** | One workspace, read-only | Watches job status and the event log; receives notifications when enabled | Managers, requesters |

### 2.1 Permission matrix

`✔` allowed · `—` denied · `own` limited to jobs the actor requested

| Capability | R-01 Admin | R-02 Owner | R-03 Curator | R-04 Designer | R-05 Requester | R-06 Reviewer | R-07 Executor | R-08 Observer |
|---|---|---|---|---|---|---|---|---|
| Create, rotate or revoke service credential | ✔ | — | — | — | — | — | — | — |
| Grant workspace roles and Drive access | ✔ | ✔ | — | — | — | — | — | — |
| Edit master templates and block markers | — | ✔ | ✔ | — | — | — | — | — |
| Edit block registry | — | ✔ | ✔ | ✔ | — | — | — | — |
| Edit recipes, skill and scripts (via repo review) | — | ✔ | — | ✔ | — | — | — | — |
| Submit and run assembly job | — | ✔ | — | ✔ | ✔ | — | — | — |
| Cancel or retry job | — | ✔ | — | — | own | — | — | — |
| Read master templates | — | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | — |
| Create, edit or delete *output* documents | — | — | — | — | — | — | ✔ (job-scoped) | — |
| Approve or reject output | — | — | — | — | — | ✔ | — | — |
| Write ledger and events | — | — | — | — | — | ✔ (decisions) | ✔ | — |
| Read ledger and events | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | — | ✔ |

---

## 3. System Goals (MVP)

Each goal is pass/fail. "Golden set" means a fixed set of request profiles with known expected output, curated for the pilot family.

| ID | Goal | Acceptance criterion | Traces to |
|---|---|---|---|
| G-01 | **Template decomposition complete** | For the pilot family, a master template exists in which every optional section is wrapped in a block marker. `scan_template` reports **0** unregistered markers, **0** registry entries without a marker, **0** duplicate IDs, **0** unbalanced or nested markers | U-03, AD-03, AD-05 |
| G-02 | **Declarative recipe** | The pilot recipe validates against the recipe schema. Every block it references exists in the registry. Every option has an explicit block mapping or an explicit "no block" | U-04, AD-06 |
| G-03 | **One-command job** | Given a valid request profile, a single skill invocation produces a **new** Google Doc in the review folder and a ledger record, with no manual edits, in ≤ NF-02 time | U-02, U-11 |
| G-04 | **Formatting fidelity** | For every retained block, the text runs, text styles, paragraph styles, list structure and table structure in the output are identical to the same block in the master revision used (structural diff of the Docs API representation). Placeholders are the only permitted differences. Passes for 100% of the golden set | U-05, AD-03 |
| G-05 | **Correct selection** | For 100% of the golden set (≥ 10 profiles covering every option at least once), the output contains **exactly** the expected block IDs in master order, with no extras and none missing | U-04, AD-06 |
| G-06 | **No leftovers** | The output contains 0 block markers and 0 unresolved placeholders. If any remain, the job fails and the output is clearly marked invalid | AD-03 |
| G-07 | **Review gate enforced** | Output is created as a draft awaiting review. A job reaches `approved` only after a recorded decision by an R-06 identity. Rejection records a reason. Approved documents are moved to the approved folder | AD-10 |
| G-08 | **Masters untouched** | After any job, successful or failed, the master template's revision ID is unchanged | AD-11 |
| G-09 | **Durable, traceable state** | Every job has a ledger record and a gap-free sequence of transition events. Re-submitting the same `request_id` doesn't create a duplicate document; it returns the existing job | Brief: persistent state |
| G-10 | **Failure safety** | If any step fails, the job ends `failed` with a structured error. A partially built output is moved to a quarantine folder or deleted, never left in the review folder | Brief: dispatch |
| G-11 | **Team portability** | A second teammate clones the repo, supplies credentials per §5.2, and runs a golden-set job successfully with **no code changes** | U-06, AD-09 |
| G-12 | **Access boundaries** | The service identity can reach only the designated Shared Drive or folders (verified by a denied-access test elsewhere). A secret scan of the repo finds no credentials | U-07, AD-07, SB-01 |
| G-13 | **Observable status** | Every transition appears in the shared event log within NF-03, and observers can see each job's current status without opening the documents | Brief: event distribution |
| G-14 | **Value check** (measured, not a gate) | Over ≥ 5 real pilot contracts, hands-on time per contract (request plus review) is recorded and compared with a manual baseline. Target is ≥ 50% reduction (ASSUMED) | U-02 |

### 3.1 Explicit non-goals (MVP)

- Drafting or rewriting contract language with AI; only pre-approved blocks are used.
- Copying formatted content between documents (additive assembly, AD-04).
- More than one document family at a time; more than one workspace.
- Unattended scheduled or queued jobs, a web UI, or a standalone service.
- Push notifications (chat, email); the event log is the MVP channel.
- Sending documents to customers, e-signature, or CRM integration.
- Legal validation of content. Reviewers own correctness.

---

## 4. Core Entities

### 4.1 Overview

```
Workspace ─┬─< Member (principal + roles)
           ├── ServiceIdentity
           ├─< DocumentFamily ─┬── MasterTemplate (Drive doc, revision-pinned)
           │                   ├─< ContentBlock (registry entry ↔ marker in master)
           │                   ├─< Placeholder
           │                   └─< AssemblyRecipe (versioned)
           ├─< SourceTemplate (legacy nested docs; input to decomposition only)
           ├─< AssemblyRequest ── AssemblyJob ─< JobStep
           │                          ├── OutputDocument
           │                          └─< ReviewDecision
           └─< Event (append-only; one per state transition)
AuditRecord: privileged actions (credential, role, master and recipe changes)
```

Common fields on every workspace-owned record: `id`, `workspace_id` (immutable), `created_at`, `updated_at`.

### 4.2 Schemas

**Workspace**: `name`, `shared_drive_id`, `folders {masters, review, approved, quarantine}`, `ledger_ref`, `status (active|suspended)`.

**Member**: `principal` (email or identity-provider subject), `roles: set<R-01…R-08>`, `status (active|removed)`.

**ServiceIdentity**: `client_email`, `key_id` (never the key itself), `scopes`, `created_by`, `rotated_at`, `status (active|revoked)`.

**DocumentFamily**: `key` (e.g. `family_a`), `display_name`, `master_template_id`, `active_recipe_version`.

**MasterTemplate**

| Field | Type | Notes |
|---|---|---|
| drive_file_id | string | Google Doc ID on the Shared Drive |
| family_key | ref | |
| approved_revision_id | string | Revision jobs must copy. A job fails if the live revision differs and curation hasn't re-approved it (see TL-08) |
| status | enum | §4.3 |

**ContentBlock** (registry entry)

| Field | Type | Notes |
|---|---|---|
| block_id | string `^[a-z0-9_]{3,64}$` | Unique within family; appears in markers |
| label | string | Human description |
| kind | enum | `section`, `clause`, `table`, `annex` |
| optional | boolean | `false` = always retained |
| source_ref | string | Which legacy SourceTemplate it came from (decomposition provenance) |
| owner | ref Member | Curator accountable |
| status | enum | §4.3 |

**Placeholder**: `key` (`^[A-Z0-9_]+$`), `type (text|date|number|currency)`, `required`, `format` (e.g. date pattern), `description`.

**AssemblyRecipe** (versioned, immutable once published)

| Field | Type | Notes |
|---|---|---|
| family_key, version | ref, integer | |
| options | list of `{option_key, allowed_values, required}` | Schema of a valid request |
| rules | list of `{when: {option_key: value}, include: [block_id], exclude: [block_id]}` | Evaluated in order. Conflicts (a block both included and excluded) fail validation |
| defaults | `{include: [block_id]}` | Blocks kept unless a rule excludes them |
| placeholder_map | `{placeholder_key: request_field}` | |
| status | enum | §4.3 |

**SourceTemplate** (legacy): `drive_file_id`, `title`, `decomposition_status (pending|mapped|retired)`, `notes`.

**AssemblyRequest**: `request_id` (caller-supplied, idempotency key), `family_key`, `options {option_key: value}`, `placeholder_values {}`, `requested_by`, `raw_input_ref` (optional pointer to the original free-text ask; never the content itself in the ledger).

**AssemblyJob**

| Field | Type | Notes |
|---|---|---|
| job_id | string | |
| request_id | ref | Unique per workspace |
| recipe_version | integer | Pinned at start |
| master_revision_id | string | Pinned at start |
| resolved_blocks | list<block_id> | Output of recipe evaluation, before any document mutation |
| output_document_id | string, nullable | |
| status | enum | §4.3 |
| error | `{code, step, message, retryable}`, nullable | |
| run_by | ref Member | Who invoked the skill |
| started_at / finished_at | timestamp | |

**JobStep**: `job_id`, `step (validate_request|resolve_blocks|copy_master|prune_blocks|fill_placeholders|strip_markers|verify_output|submit_for_review)`, `status (pending|running|succeeded|failed|skipped)`, `attempts`, `duration_ms`, `error`.

**OutputDocument**: `drive_file_id`, `name` (§6.5 convention), `folder (review|approved|quarantine)`, `created_from_revision`.

**ReviewDecision**: `job_id`, `reviewer`, `decision (approved|rejected)`, `reason` (required on reject), `decided_at`.

**Event**: §6.4. **AuditRecord**: `actor`, `action`, `target`, `outcome`, `occurred_at`.

### 4.3 Lifecycle state transitions

Each transition appends exactly one Event. Unlisted transitions are illegal.

**SourceTemplate** (decomposition phase)
```
pending → mapped → retired
```

**ContentBlock**
```
proposed → active → deprecated → removed
```
A block can't be `removed` while any published recipe references it.

**MasterTemplate**
```
draft → in_review → approved ──(curator edits)──→ draft
                       └────→ retired
```
Only `approved` masters, at their `approved_revision_id`, can be copied by jobs.

**AssemblyRecipe**
```
draft → validated → published → deprecated
   ↑______↓ (any edit)
```

**AssemblyJob**
```
requested → validating → resolving → building → verifying → awaiting_review ─┬→ approved (terminal)
     │           │            │           │            │                     └→ rejected (terminal)
     └───────────┴────────────┴───────────┴────────────┴──→ failed (terminal)
requested/validating/resolving → cancelled (terminal, by requester)
failed or rejected → (retry) creates a NEW job with a new request_id that references the old one
```

| From | To | Actor | Guard and effect |
|---|---|---|---|
| requested | validating | Executor | Request parsed |
| validating | resolving | Executor | Options and placeholders valid against recipe; no existing job with same `request_id` (otherwise return that job) |
| resolving | building | Executor | `resolved_blocks` computed and recorded **before** any Drive write |
| building | verifying | Executor | Master copied, unselected blocks pruned, placeholders filled, markers stripped |
| verifying | awaiting_review | Executor | G-04, G-05 and G-06 checks pass; output in review folder |
| any active | failed | Executor | Any step error; partial output quarantined (G-10) |
| awaiting_review | approved | Reviewer | Decision recorded; document moved to approved folder |
| awaiting_review | rejected | Reviewer | Reason required; document stays in review or quarantine for reference |

### 4.4 Invariants

1. A job never writes to a master template or source template.
2. `resolved_blocks` is fixed before the first document mutation and never changes afterwards.
3. An output document belongs to exactly one job.
4. Only Reviewer decisions move a job to `approved`.
5. Published recipes are immutable; jobs pin recipe version and master revision.
6. Block markers are balanced, not nested, and unique per master.
7. Credentials never appear in the repo, the ledger, events or documents.

---

## 5. Feature Constraints

### 5.1 Non-functional bounds (all ASSUMED pending Q-01 and Q-03)

| ID | Dimension | Bound |
|---|---|---|
| NF-01 | Volume | Designed for ≤ 50 jobs/day per workspace in MVP; one job at a time per user session |
| NF-02 | Job duration | ≤ 2 min wall-clock from `requested` to `awaiting_review` for a master of ≤ 60 blocks and ≤ 100 placeholders |
| NF-03 | Event visibility | Each transition written to the shared event log ≤ 10 s after it happens |
| NF-04 | Master size | ≤ 60 optional blocks, ≤ 100 placeholders, ≤ 150 pages per master (beyond this, split the family) |
| NF-05 | Determinism | Same request + same recipe version + same master revision → the same set and order of blocks, every time |
| NF-06 | Reliability | Transient API errors (rate limits, 5xx) are retried with exponential backoff, ≤ 5 attempts per call. Overall golden-set pass rate is 100% |
| NF-07 | Retention | Ledger and events kept ≥ 1 year (ASSUMED; align with the organisation's contract-records policy) |
| NF-08 | Setup time | A new teammate can run a job in ≤ 30 min following the README (G-11) |

### 5.2 Security boundaries

| ID | Boundary | Rule |
|---|---|---|
| SB-01 | **Least-privilege Drive access** | The service identity is a member only of the designated Shared Drive (or specific folders), with the lowest role that can create, edit and move files there. It has no domain-wide delegation |
| SB-02 | **Credential custody** | The service-account key is never committed. Each runtime loads it from a path outside the repo or from an environment variable (`GOOGLE_APPLICATION_CREDENTIALS`). `.gitignore` blocks `*.json` under `credentials/` and common key patterns. A pre-commit secret scan is required. Distribution of the key to teammates follows R-01's process (password manager or secret store), never chat or email |
| SB-03 | **Key lifecycle** | Keys are rotated at least every 90 days and immediately when a member with key access leaves. Revocation is tested in G-12 |
| SB-04 | **Minimal API scopes** | Request only the Docs and Drive scopes the scripts require. Downstream design must document each scope with its justification (VERIFY: whether a narrower Drive scope works for files the service account didn't create) |
| SB-05 | **Separation of duties** | Changes to masters (R-03) and to recipes or code (R-04) go through review: a Drive approval step for masters, pull-request review for the repo. Optional setting: the requester can't be the reviewer of their own job |
| SB-06 | **Data minimisation** | The ledger stores IDs, option values and statuses, not contract bodies. Customer-identifying placeholder values are stored only if NF-07 policy allows; otherwise store a hash or reference |
| SB-07 | **AI data handling** | Contract content processed by Claude falls under the organisation's Claude Team plan data terms and internal policy. Confirm acceptability with the Workspace Owner before processing real customer data |
| SB-08 | **No external transmission** | The engine never emails, shares externally, or changes the sharing settings of output documents. Sharing outside the organisation is a manual human act after approval |
| SB-09 | **Audit** | Credential issue and rotation, role changes, master approvals and recipe publications produce AuditRecords |

### 5.3 Technical limits and accepted trade-offs

| ID | Limit | Consequence and design rule |
|---|---|---|
| TL-01 | Docs API edits are index-based | Deleting a range shifts every later index. Pruning **must** delete blocks in descending index order within a single batched update, after reading the document once |
| TL-02 | Block boundaries must align with structure | A marker pair must enclose whole paragraphs or whole tables. Partial-table-row blocks and blocks that start mid-paragraph are rejected by `scan_template` |
| TL-03 | Body-only scope | MVP processes the document body. Blocks or placeholders in headers, footers or footnotes are unsupported until Q-07 is resolved |
| TL-04 | Marker visibility | MVP markers are visible text tokens, so curators can see and maintain them; they're stripped from output. Hidden named ranges are an alternative to evaluate later (VERIFY whether they survive file copy and editing) |
| TL-05 | No cross-document formatted copy | See CORR-02 and AD-04 |
| TL-06 | Service-account storage | Service accounts may lack personal Drive storage quota, so outputs must be created inside a Shared Drive (AD-08, VERIFY) |
| TL-07 | API quotas | Google API per-minute quotas apply per project. Scripts batch mutations into as few calls as possible and back off on rate-limit errors (NF-06) |
| TL-08 | Concurrent curation | If a curator edits a master while a job is copying it, the job may capture an unapproved revision. Jobs compare the live revision with `approved_revision_id` and fail on mismatch |
| TL-09 | Spreadsheet ledger concurrency | Two teammates writing the ledger simultaneously can collide. Writes are append-only rows with unique IDs; no in-place edits except the job's status cell |
| TL-10 | Claude judgment is advisory | Claude may map free-text requests to options but cannot add blocks that the recipe doesn't resolve. Ambiguous requests are sent back to the requester as a question, not guessed |
| TL-11 | Product facts drift | Claude plan features, seat types and Google API behaviours change. Items tagged VERIFY must be re-checked at build time |

---

## 6. Output Specifications

### 6.1 Repository layout (the Claude Code project)

```
document-assembly/                      # local folder; Claude Code runs here; synced via git
├── .claude/
│   └── skills/
│       └── document-assembly/
│           ├── SKILL.md                # procedure Claude follows (see 6.2)
│           ├── scripts/
│           │   ├── gdocs_client.py     # auth, retries/backoff, thin Docs/Drive/Sheets wrapper
│           │   ├── scan_template.py    # validate markers in a master vs the registry
│           │   ├── assemble.py         # copy → prune → fill → strip; writes ledger + events
│           │   ├── verify_output.py    # fidelity diff, selection check, leftover check
│           │   └── review.py           # record approve/reject; move file
│           └── reference/
│               ├── recipe_schema.md
│               └── marker_syntax.md
├── config/
│   ├── workspace.yaml                  # IDs of shared drive, folders, ledger. NO secrets
│   ├── registry/<family_key>.yaml      # ContentBlock + Placeholder entries
│   └── recipes/<family_key>.v<N>.yaml  # AssemblyRecipe versions
├── requests/examples/                  # sample AssemblyRequest files
├── tests/golden/<family_key>/          # golden request profiles + expected block lists
├── _docs/MVP_scope_plan.md
├── README.md                           # teammate setup (NF-08)
└── .gitignore                          # credentials/, *.key.json, .env
```

### 6.2 Skill and script contracts

**`SKILL.md` frontmatter**: `name: document-assembly`; `description:` must trigger on requests to assemble, generate or build a document from templates for a request or customer, and must *not* trigger on general document editing.

**SKILL.md body must instruct Claude to:**
1. Turn the user's ask into an AssemblyRequest (§6.3). If any option or required placeholder is missing or ambiguous, **ask the user**; don't guess (TL-10).
2. Show the user the resolved block list and placeholder values, then proceed.
3. Run `assemble.py`, then `verify_output.py`. Report the output link and status, or the structured error.
4. Never edit document text directly, never edit masters, and never mark a job approved.

**Script CLI contract** (all scripts):

| Script | Invocation | Success output (stdout, JSON) | Failure |
|---|---|---|---|
| `scan_template.py` | `--family <key>` | `{ok, blocks_found, issues: []}` | exit 2 with `issues` populated |
| `assemble.py` | `--request <path> [--dry-run]` | `{job_id, status, output_document_id, resolved_blocks}` | exit 1 with `{job_id, status:"failed", error:{code, step, message, retryable}}` |
| `verify_output.py` | `--job <job_id>` | `{job_id, fidelity:"pass", selection:"pass", leftovers:0}` | exit 1 with per-check detail |
| `review.py` | `--job <job_id> --decision approve\|reject [--reason ...]` | `{job_id, status}` | exit 1. Refuses unless the caller holds R-06 per `workspace.yaml` |

`--dry-run` resolves blocks and validates without touching Drive. It's required for golden-set selection tests (G-05).

**Error codes**: `invalid_request`, `unknown_option`, `missing_placeholder`, `recipe_conflict`, `master_revision_mismatch`, `marker_error`, `drive_permission_denied`, `rate_limited`, `verification_failed`, `duplicate_request` (returns existing job), `internal`.

### 6.3 Assembly request format

```yaml
request_id: "REQ-2026-0001"        # unique; idempotency key
workspace_id: "ws_main"
family_key: "family_a"
options:
  service_tier: "premium"
  payment_terms: "net_30"
  include_annex_sla: true
placeholder_values:
  PARTY_NAME: "Example Customer Ltd"
  EFFECTIVE_DATE: "2026-11-01"
requested_by: "member_id"
```

### 6.4 Event and ledger formats

**`jobs` tab**: one row per job with the AssemblyJob fields (§4.2); `status` is the only cell updated in place.

**`events` tab** (append-only):

```json
{
  "event_id": "evt_…",
  "workspace_id": "ws_main",
  "job_id": "job_…",
  "sequence": 4,
  "event_type": "job.awaiting_review",
  "from": "verifying",
  "to": "awaiting_review",
  "actor": "service|member_id",
  "occurred_at": "2026-10-22T17:05:00Z",
  "detail": { "output_document_id": "…", "blocks": 14 }
}
```

Event type naming is `<entity>.<to_status>`. Observers filter by `job_id` or `event_type`.

### 6.5 Output document conventions

- **Name:** `<family_key>__<request_id>__<YYYY-MM-DD>__DRAFT` (`__DRAFT` is removed on approval).
- **Location:** `review/` → `approved/` on approval; `quarantine/` on failure (G-10).
- **Content:** retained blocks in master order, all placeholders filled, no markers, formatting identical to the master revision (G-04).
- **Traceability:** the job ID is recorded in the document's Drive description/properties, so any document can be traced back to its job, recipe version and master revision.

### 6.6 Block marker syntax (master templates)

```
[[BLOCK:block_id]]
…formatted content: whole paragraphs and/or whole tables…
[[/BLOCK:block_id]]
```
Placeholders: `{{PLACEHOLDER_KEY}}`. Markers sit on their own paragraphs. `scan_template.py` enforces the rules in TL-02 and invariant 6.

### 6.7 MVP delivery phases

| Phase | Output | Exit criterion |
|---|---|---|
| P0 Access setup | Cloud project, APIs enabled, service account, Shared Drive membership, credential custody process | G-12 denied-access and secret-scan tests pass |
| P1 Decomposition | Pilot master template with markers, block registry, legacy sources mapped | G-01 passes |
| P2 Rules | Recipe v1 and golden set | G-02 and G-05 (dry-run) pass |
| P3 Build | Skill and scripts | G-03, G-04, G-06, G-08, G-09 and G-10 pass on the golden set |
| P4 Team rollout | README, second-teammate run, review flow | G-07, G-11 and G-13 pass |
| P5 Pilot measurement | ≥ 5 real contracts | G-14 recorded; go/no-go for a second family |

### 6.8 Expected downstream artifacts

Each must cite the IDs used here (U-, AD-, CORR-, G-, NF-, SB-, TL-):

1. Fidelity spike report confirming AD-03 on the real pilot master (run before P3).
2. Detailed design of the scripts and the Google API calls each one makes, with scopes (SB-04).
3. Test plan mapping every G-xx to an automated or manual check.
4. Teammate README and credential-custody runbook.
5. Threat model reviewing §5.2.

---

## Appendix A: Traceability Matrix

| Goal | User and brief signals | Decisions | Entities | Constraints |
|---|---|---|---|---|
| G-01 Decomposition | U-03 | AD-03, AD-05 | SourceTemplate, MasterTemplate, ContentBlock | TL-02, TL-04, NF-04 |
| G-02 Recipe | U-04 | AD-06 | AssemblyRecipe | TL-10 |
| G-03 One-command job | U-02, U-08, U-11 | AD-01, AD-02 | AssemblyRequest, AssemblyJob | NF-02 |
| G-04 Fidelity | U-05 | AD-03, AD-04 | OutputDocument | TL-01, TL-05 |
| G-05 Selection | U-04 | AD-06 | AssemblyRecipe, AssemblyJob | NF-05 |
| G-06 No leftovers | U-05 | AD-03 | OutputDocument | §6.6 |
| G-07 Review gate | U-05 | AD-10 | ReviewDecision | SB-05, SB-08 |
| G-08 Masters untouched | conversation | AD-11 | MasterTemplate | TL-08 |
| G-09 Durable state | brief | AD-12 | AssemblyJob, Event | TL-09, NF-07 |
| G-10 Failure safety | brief | AD-01 | JobStep | NF-06 |
| G-11 Portability | U-06, U-09, U-10 | AD-09 | Workspace, Member | NF-08, SB-02 |
| G-12 Access | U-07 | AD-07, AD-08 | ServiceIdentity | SB-01–SB-04, TL-06 |
| G-13 Observable status | brief | AD-12 | Event | NF-03 |
| G-14 Value | U-02 | AD-14 | — | — |
