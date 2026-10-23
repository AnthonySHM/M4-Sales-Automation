# A Workflow Initiative

**Spec-driven, multi-agent development playbook, adapted to the Template-Driven Document Assembly Engine**

> Converted from `A_Workflow_Initiative.pdf` (13 pages). The explanatory text, step order and references are reproduced from the source.
>
> **What changed:** each step's **PROMPT** has been rewritten to match `_docs/MVP_scope_plan.md` (`SPEC-MVP-002` v0.2.0, the contract-assembly project). The source prompt describes a generic web service (HTTP APIs, ORM, Docker); this project is a Claude Code skill with bundled Python scripts working on Google Drive. Each original prompt is preserved verbatim in a collapsible block under its adapted version.
>
> IDs such as `AD-03`, `G-04` or `SB-02` refer to entries in the MVP scope plan.

---

## How the playbook maps to the MVP scope plan

| Step | Output file | Scope plan sections it draws on | Main adaptation |
|---|---|---|---|
| 1 | `_docs/MVP_scope_plan.md` | All | Adds the project's context and the plan's ID and provenance scheme. **Already completed (v0.2.0)** |
| 2 | Git baseline commit | SB-02 | `.gitignore` for credentials *before* the first commit |
| 3 | `_docs/architecture.md` | AD-01–AD-14, §6.1–§6.4, SB-04 | Script CLI and JSON Schema contracts replace OpenAPI; ledger adapter replaces ORM; `doctor` health check replaces HTTP health endpoints |
| 4 | `_docs/tasks.md` | §6.7 delivery phases | Tasks follow phases P0–P5; human-only tasks labelled `HUMAN` |
| 5 | GitHub Issues | §6.7 | Phase and `human` labels; dependencies rewritten to issue numbers |
| 6 | `_docs/task-template.md` | G-, AD-, SB-, TL-, §3.1 | Criteria and constraints cite scope plan IDs |
| 7 | `_docs/team/pm.md` | §1.2 origin tags, §1.6 open questions | PM must not guess answers to open questions or `VERIFY` items |
| 8 | `_docs/team/software-engineer.md` | §6.2 error codes, NF-04, SB-02 | Domain error types and boundary values from the plan |
| 9 | `_docs/team/qa-engineer.md` | G-03–G-10, TL-01–TL-04 | Golden-set E2E on a sandbox Shared Drive; fidelity check |
| 10 | `_docs/process.md` | AD-10, SB-05 | Human gates in the graph; credential and sandbox rules for parallel worktrees |
| 11 | `AGENTS.md`, `CLAUDE.md` | §6.1, SB-01–SB-08 | Project commands and safety rules; adds the scope plan to the index |
| 12 | Execution loop on Task #1 | All | Task #1 = runnable skeleton plus `doctor` plus green tests |

---

## Step 1: Create `_docs/MVP_scope_plan.md`

Spec-Driven Development serves as foundational context infrastructure rather than a disposable preamble [1]. When highly capable artificial intelligence (AI) coding agents receive ambiguous prompts, they tend to fill information gaps with unwarranted assumptions [1]. A weak coding agent that misunderstands a specification generates broken code, whereas a highly capable coding agent creates complex multi-file architectures, wires components together, and writes passing tests for features that were never requested [1]. To eliminate this architectural drift, engineering teams must shift from manual code typing to precise requirement specification and rigorous verification [1].

Establishing a robust project scope requires an interactive dictation or structured brainstorming dialogue to systematically define domain-agnostic product goals, system entities, user roles, feature constraints, and output specifications [1]. A critical component of this foundational phase is requirement provenance—preserving the evidence, user signals, architectural decisions, and explicit rationale behind every specification [1]. Retaining provenance ensures that subagents can challenge stale assumptions, respect component boundaries, and maintain alignment as the project evolves [1].

> **Status:** completed. `_docs/MVP_scope_plan.md` v0.2.0 exists. Use the prompt below only to regenerate or revise it.

### PROMPT (adapted)

```text
claude "You are an expert systems analyst. Analyse the raw project idea and the project context below and formulate a comprehensive, domain-agnostic MVP scope specification saved strictly to '_docs/MVP_scope_plan.md'. RAW PROJECT IDEA: 'Build a decoupled, multi-tenant automated workflow processing engine with real-time event distribution, user access controls, persistent state tracking, and automated task dispatching.' PROJECT CONTEXT (pilot application): a team edits customer contracts in Google Drive that are built from nested templates ('templates of templates'); which sections and tables are used depends on the customer; heavy formatting must be preserved because these are contracts; the whole team must be able to use the tool; Google access must not depend on one person's account; assembly runs as a Claude Code skill with bundled Python scripts, shared through a git repository, with no standalone application; every output needs human approval. REQUIREMENTS: 1. Structure the document into explicit sections: Document Metadata & Requirement Provenance, Domain-Agnostic User Roles, System Goals, Core Entities, Feature Constraints, and Output Specifications. 2. Under 'Document Metadata & Requirement Provenance', capture user signals (U-xx), architectural decisions (AD-xx) each with an origin tag (USER, AGREED, INFERRED, ASSUMED, CORRECTED, VERIFY) and a revisit trigger, corrections (CORR-xx), decision history and open questions (Q-xx), and map each brief keyword (decoupled, multi-tenant, real-time events, access controls, persistent state, dispatching) to its MVP treatment, so downstream subagents can challenge stale assumptions. 3. Under 'Domain-Agnostic User Roles', define functional actors (System Administrator, Workspace Owner, Content Curator, Workflow Designer, Job Requester, Reviewer, Task Executor, Event Observer) with a permission matrix and no domain-specific bias. 4. Under 'System Goals', specify checkable pass/fail targets (G-xx) for the MVP and list explicit non-goals. 5. Under 'Core Entities', outline abstract objects (workspace, master template, content block, assembly recipe, assembly request, assembly job, output document, review decision, event), data schemas, lifecycle state transitions and invariants. 6. Under 'Feature Constraints', record non-functional bounds (NF-xx), security boundaries (SB-xx) and technical limits (TL-xx). 7. Under 'Output Specifications', define the repository layout, skill and script contracts, request, ledger and event formats, output document conventions and delivery phases. 8. If '_docs/MVP_scope_plan.md' already exists, read it first, keep existing IDs stable, record every change in the decision history, and never silently drop a decision. 9. Ensure directory '_docs' exists and save the result directly to '_docs/MVP_scope_plan.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "You are an expert systems analyst. Analyse the raw project idea below and formulate a comprehensive, domain-agnostic MVP scope specification saved strictly to '\_docs/MVP_scope_plan.md'. RAW PROJECT IDEA: 'Build a decoupled, multi-tenant automated workflow processing engine with real-time event distribution, user access controls, persistent state tracking, and automated task dispatching.' REQUIREMENTS: 1. Structure the document into explicit sections: Document Metadata & Requirement Provenance, Domain-Agnostic User Roles, System Goals, Core Entities, Feature Constraints, and Output Specifications. 2. Under 'Document Metadata & Requirement Provenance', explicitly capture the user signals, architectural decisions, and decision history behind every specification so downstream subagents can challenge stale assumptions. 3. Under 'Domain-Agnostic User Roles', define functional system actors (e.g., System Administrator, Workspace Owner, Task Executor, Event Observer) without domain-specific bias. 4. Under 'System Goals', specify checkable functional targets for the Minimum Viable Product (MVP). 5. Under 'Core Entities', outline abstract domain objects, data schemas, and lifecycle state transitions. 6. Under 'Feature Constraints', record non-functional bounds, security boundaries, and technical limits. 7. Ensure directory '\_docs' is created if missing and save the resulting file directly to '\_docs/MVP_scope_plan.md'."

</details>

---

## Step 2: Bootstrap Repository & Baseline Commit

Repository bootstrapping, atomic initialisation, and baseline tracking establish an uncorrupted reference checkpoint in version control [1]. Committing the baseline scope plan (`_docs/MVP_scope_plan.md`) prior to generating implementation source code guarantees that the architectural intent remains preserved in the repository history [1].

Automated coding agents execute rapid multi-file modifications across complex codebases. Frequent, milestone-driven Git commits provide an essential rollback mechanism when agents produce architectural drift, introduce regressions, or execute invalid refactoring chains [1]. Staging and committing baseline documentation establishes a clean version history, allowing engineering teams to isolate, review, and reset state at every structural milestone [1].

### PROMPT (adapted)

```text
claude "Run system environment commands to bootstrap the baseline repository state: 1. Initialise a Git repository in the project root and create directory '_docs' if it does not exist. 2. Before staging anything, create '.gitignore' excluding 'credentials/', '*.key.json', any Google service-account key file, '.env', '.venv/', '__pycache__/' and '.worktrees/' (MVP scope plan SB-02). 3. Confirm that no credential or key file exists anywhere in the working tree; if one is found, stop and report it instead of committing. 4. Stage '.gitignore', '_docs/MVP_scope_plan.md' and '_docs/MVP_scope_plan.v0.1.0-generic.md'. 5. Execute an initial baseline commit with the exact message 'docs: bootstrap project repository and baseline MVP scope plan'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> claude "Run system environment commands to bootstrap the baseline repository state: initialise a Git repository, create directory '\_docs' if it does not exist, stage '\_docs/MVP_scope_plan.md', and execute an initial baseline commit with the exact message 'docs: bootstrap project repository and baseline MVP scope plan'."

</details>

---

## Step 3: Create `_docs/architecture.md`

Translating product scope into a technical architecture requires evaluating technology stacks, system boundaries, and operational mechanisms prior to code generation [1, 2]. Decoupling system components simplifies subagent context windows by constraining execution paths to isolated modules, preventing agent context saturation and reducing token overhead [1, 2].

A robust systemic architecture specification must define multi-tiered component layouts, formal contract standards (such as OpenAPI or AsyncAPI specifications for backend-frontend contracts) [2], persistent storage isolation layers (such as Object-Relational Mapping encapsulate schema migration pathways) [2], and containerised operational observability hooks (such as health check endpoints, structured JSON logging, and container configuration) [2]. Selecting modular, well-decoupled frameworks enhances developer agent velocity by allowing subagents to inspect isolated API contracts and interfaces without loading entire codebase structures into context [1, 2].

> **Adaptation note:** the MVP has no server or HTTP API (AD-02), so the playbook's *contract*, *storage isolation* and *observability* requirements are applied to the script CLIs, JSON Schemas, the ledger adapter and a `doctor` command.

### PROMPT (adapted)

```text
claude "Inspect the specification and requirement provenance in '_docs/MVP_scope_plan.md'. Formulate a production-grade architectural specification and write it to '_docs/architecture.md'. STRICT RULES: 1. Do NOT generate application implementation source code files. 2. Respect the scope plan's decisions: Claude Code skill orchestration with bundled Python scripts (AD-01, AD-02), subtractive master-template assembly (AD-03), declarative recipes (AD-06), service-account access on a Shared Drive (AD-07, AD-08), git distribution (AD-09), mandatory human review (AD-10), immutable masters (AD-11) and the shared ledger (AD-12). Do not silently depart from any decision: if you recommend a change, write it as a proposal citing the decision ID, its revisit trigger and your evidence. 3. Detail tech stack choices (Python version, Google API client libraries, schema validation, test framework, dependency pinning and packaging), articulating trade-offs between architectural complexity and agent execution velocity. 4. Define modular component design, enforcing strict decoupling between interface components (SKILL.md and script CLI entry points), service layers (request validation, recipe resolution, document operations, output verification, review) and data storage (ledger adapter), so each module can be built and tested by a coding subagent without loading the rest of the codebase into context. 5. Define formal contracts in place of HTTP APIs: JSON Schemas for the assembly request, recipe, block registry, job record and event (scope plan §6.3–§6.4); the CLI contract for every script with arguments, JSON stdout, exit codes and error codes (§6.2); and the exact Google Docs, Drive and Sheets API operations and OAuth scopes each module uses, with a justification per scope (SB-04). An AsyncAPI document for the event log is optional. 6. Specify the data isolation layer as a storage-agnostic repository interface over the job ledger (Google Sheet in MVP, replaceable by a database per AD-12), covering mandatory workspace_id on every record, append-only event rules, idempotency on request_id, concurrency handling (TL-09) and schema-version migration. 7. Detail runtime and observability: a reproducible Python environment (a container image is optional and must be justified), a 'doctor' health-check command verifying credentials, API reachability, Shared Drive membership and master revision, structured JSON logging correlated by job_id and request_id, and the test-environment strategy (fakes for Google APIs in unit tests, a sandbox Shared Drive for end-to-end tests, never real customer data). 8. Include a traceability table mapping every component to the scope plan IDs it satisfies, and list the VERIFY items that must be re-checked against current vendor documentation. 9. Save the final output directly to '_docs/architecture.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Inspect the specification and requirement provenance in '\_docs/MVP_scope_plan.md'. Formulate a production-grade architectural specification and write it to '\_docs/architecture.md'. STRICT RULES: 1. Do NOT generate application implementation source code files. 2. Detail tech stack choices, articulating trade-offs between architectural complexity and agent execution velocity. 3. Define modular component design, enforcing strict decoupling between interface components, service layers, and data storage to minimise context window overhead for coding subagents. 4. Define formal API contracts (OpenAPI/AsyncAPI specifications) establishing explicit request/response schemas, endpoint paths, and authentication mechanics. 5. Specify data isolation layers using database-agnostic Object-Relational Mapping (ORM) design, schema migration pathways, and persistent state rules. 6. Detail containerisation and observability specifications, including Docker runtime hooks, health check contracts, and structured logging formats. 7. Save the final output directly to '\_docs/architecture.md'."

</details>

---

## Step 4: Create `_docs/tasks.md`

Decomposing monolithic specifications into a structured task backlog prevents subagent hallucination and context overload [1]. Adhering to Google Code Review standards regarding Change Lists (CLs) requires keeping work items small, atomic, focused on a single change, and easy to review [1].

Task decomposition must enforce strict operational constraints: every task must be small enough to be completed within a single subagent execution loop session, completely self-contained so it can be understood without inspecting adjacent tasks, and sequentially mapped with explicit dependency trees [1]. Furthermore, Task #1 must universally be designated as bootstrapping a barebones runnable project repository equipped with a green, passing automated test suite [1].

### PROMPT (adapted)

```text
claude "Read '_docs/MVP_scope_plan.md' and '_docs/architecture.md'. Decompose the system architecture into a sequentially ordered, atomic task backlog saved strictly to '_docs/tasks.md'. STRICT CONSTRAINTS & FORMATTING RULES: 1. Task #1 MUST strictly be setting up a barebones, runnable repository with baseline dependencies, the skill folder skeleton, a 'doctor' health-check command (running against fakes, no live Google calls), and a green, passing automated test suite. 2. Order the remaining tasks by the scope plan's delivery phases (P0 access setup, P1 decomposition, P2 rules, P3 build, P4 team rollout, P5 pilot measurement). Work that needs a person, such as creating the service account, sharing the Shared Drive, marking up the master template, approving recipes or answering open questions (Q-xx), MUST be marked 'HUMAN' in its title and never assigned to coding subagents. 3. Enforce small Change List (CL) sizing per task: each task must be small enough to complete within a single subagent context loop session. 4. Every task entry MUST strictly adhere to the following template:
## <number>. <title>
Goal: <one line describing the functional outcome> Description: <two or three sentences detailing implementation scope> Dependencies: <list of prerequisite task numbers or None>
5. Inside each Description, name the scope plan IDs (G-, AD-, SB-, TL-) the task advances. 6. Ensure tasks are fully self-contained and independent, enabling isolated execution. 7. Do NOT write application source code files during this session. 8. Output the backlog directly to '_docs/tasks.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Read '\_docs/MVP_scope_plan.md' and '\_docs/architecture.md'. Decompose the system architecture into a sequentially ordered, atomic task backlog saved strictly to '\_docs/tasks.md'. STRICT CONSTRAINTS & FORMATTING RULES: 1. Task #1 MUST strictly be setting up a barebones, runnable repository with baseline dependencies, health check routing, and a green, passing automated test suite. 2. Enforce small Change List (CL) sizing per task—each task must be small enough to complete within a single subagent context loop session. 3. Every task entry MUST strictly adhere to the following template:
> \#\# \<number\>. \<title\>
> Goal: \<one line describing the functional outcome\> Description: \<two or three sentences detailing implementation scope\> Dependencies: \<list of prerequisite task numbers or None\> 4. Ensure tasks are fully self-contained and independent, enabling isolated execution. 5. Do NOT write application source code files during this session. 6. Output the backlog directly to '\_docs/tasks.md'."

</details>

---

## Step 5: Migrate Backlog to GitHub Issues

Transitioning static task backlogs (`_docs/tasks.md`) into a dynamic issue tracking system creates an authoritative, single source of truth for automated subagents [1]. Static markdown backlogs risk local state corruption and race conditions when queried concurrently by autonomous agents [1].

Utilising the GitHub CLI (`gh issue create`) enables programmatic issue creation and state updates, allowing subagent orchestration loops to query real-time task statuses, append verification comments, and transition issue states dynamically [1]. Once exported, GitHub Issues become the canonical task backlog, ensuring that stale local files are superseded by remote issue states [1].

### PROMPT (adapted)

```text
claude "Verify connectivity to the GitHub repository via the GitHub CLI ('gh'). Read '_docs/tasks.md' and programmatically create a structured GitHub Issue for every task in the backlog. EXECUTION INSTRUCTIONS: 1. Check remote GitHub repository connection using 'gh repo view'. If unconnected or missing remote URL, handle gracefully or report error. 2. Sequentially parse '_docs/tasks.md' to extract each task's number, title, goal, description, and dependencies. 3. Create any missing labels: one per delivery phase ('phase:P0' to 'phase:P5') and 'human' for tasks marked HUMAN. 4. Iterate through all tasks and programmatically execute 'gh issue create' with structured '--title', '--body' and '--label' flags incorporating goal, description, dependency details and the scope plan IDs the task cites. 5. Once every issue exists, edit each issue body so its dependencies reference the new GitHub issue numbers. 6. Verify created issues return valid GitHub Issue URLs and numbers. 7. Print a summary mapping table to stdout displaying local task numbers mapped to newly created GitHub Issue numbers."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Verify connectivity to the GitHub repository via the GitHub CLI ('gh'). Read '\_docs/tasks.md' and programmatically create a structured GitHub Issue for every task in the backlog. EXECUTION INSTRUCTIONS: 1. Check remote GitHub repository connection using 'gh repo view'. If unconnected or missing remote URL, handle gracefully or report error. 2. Sequentially parse '\_docs/tasks.md' to extract each task's number, title, goal, description, and dependencies. 3. Iterate through all tasks and programmatically execute 'gh issue create' with structured '--title' and '--body' flags incorporating goal, description, and dependency details. 4. Verify created issues return valid GitHub Issue URLs and numbers. 5. Print a summary mapping table to stdout displaying local task numbers mapped to newly created GitHub Issue numbers."

</details>

---

## Step 6: Create `_docs/task-template.md`

Grooming raw backlog tasks into unambiguous, executable specifications requires a standardised issue grooming template [1]. Unstructured task descriptions force coding agents to invent implementation details, leading to unwarranted architectural assumptions [1].

A robust task template must enforce a mandatory four-part issue layout: Goal, Acceptance Criteria, Out of Scope, and Constraints [1]. Acceptance criteria must be framed as checkable, binary pass/fail statements that can be verified directly on screen or via automated test suites [1]. The "Out of Scope" section acts as an explicit boundary guard against feature creep, mandating that newly discovered requirements generate linked follow-up issues rather than silent drops [1]. The "Constraints" section defines precise file boundaries, library dependencies, and architectural rules to restrict subagent scope drift [1].

### PROMPT (adapted)

```text
claude "Generate a standardised Markdown task grooming template and save it directly to '_docs/task-template.md'. TEMPLATE LAYOUT REQUIREMENTS: The generated file must contain exactly four Markdown section headers with detailed guidance for issue groomers: ## Goal [One or two sentences defining the precise functional state upon completion, naming the MVP scope plan goal (G-xx) it advances.] ## Acceptance criteria - [ ] [Checkable statement 1: Binary pass/fail assertion observable on screen, in a script's JSON output or in test logs] - [ ] [Checkable statement 2: Explicit handling of boundary conditions or edge cases, such as zero blocks, the maximum block and placeholder counts (NF-04), unknown options, unbalanced markers and master revision mismatch] ## Out of scope - [Features or refactorings not required for this task, explicitly linked to follow-up GitHub Issue #NUMBER; MVP non-goals from scope plan section 3.1 are cited, not reopened] ## Constraints - [Allowed file modification paths and module boundaries from '_docs/architecture.md'] - [Mandatory or prohibited libraries and framework patterns] - [Architectural and contract guidelines to respect, cited by scope plan ID (AD-, SB-, TL-)] - [Safety rules: no credentials in code, tests or logs; no writes to master templates; no live Google API calls in unit tests] Save the final template strictly to '_docs/task-template.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Generate a standardised Markdown task grooming template and save it directly to '\_docs/task-template.md'. TEMPLATE LAYOUT REQUIREMENTS: The generated file must contain exactly four Markdown section headers with detailed guidance for issue groomers: \#\# Goal [One or two sentences defining the precise functional state upon completion.] \#\# Acceptance criteria - [ ] [Checkable statement 1: Binary pass/fail assertion observable on screen or via test logs] - [ ] [Checkable statement 2: Explicit handling of boundary conditions or edge cases] \#\# Out of scope - [Features or refactorings not required for this task, explicitly linked to follow-up GitHub Issue \#NUMBER] \#\# Constraints - [Allowed file modification paths and module boundaries] - [Mandatory or prohibited libraries and framework patterns] - [Architectural and contract guidelines to respect] Save the final template strictly to '\_docs/task-template.md'."

</details>

---

## Step 7: Create Product Manager Agent Role (`_docs/team/pm.md`)

Establishing strict operational boundaries between subagents prevents role overlap and accidental source code corruption [1]. The Product Manager (PM) subagent is designed as a specialised specification groomer that processes raw backlog issues into actionable requirements [1].

The PM subagent operates under a strict NO-CODE rule: it is prohibited from editing or writing implementation source code [1]. Its primary duty is to analyse open GitHub Issues, identify unconsidered edge cases, rewrite issue descriptions using `_docs/task-template.md`, frame screen-checkable acceptance criteria, and enforce requirement provenance [1]. If a task scope uncovers necessary work beyond the current issue, the PM subagent must file a new follow-up GitHub issue using `gh issue create` and explicitly reference it in the "Out of Scope" section [1].

### PROMPT (adapted)

```text
claude "Create the Product Manager subagent operational persona document and save it strictly to '_docs/team/pm.md'. ROLE DEFINITION & REQUIREMENTS: 1. Operational Persona: You are the Product Manager (PM) Subagent. 2. Primary Responsibility: Groom raw GitHub Issues into fully specified, executable issue descriptions before software engineers write code. 3. Strict No-Code Boundary: The PM subagent MUST NOT write or edit source code, tests, application logic, recipes, the block registry or master templates. 4. Workflow Directives: - Read the designated raw GitHub Issue. - Analyse requirements against '_docs/MVP_scope_plan.md' and '_docs/architecture.md', citing the scope plan IDs (U-, AD-, G-, NF-, SB-, TL-) behind every requirement to preserve provenance. - Respect origin tags: decisions tagged USER or AGREED are held; ASSUMED and INFERRED decisions may be challenged by filing a proposal issue, never by silently changing scope; CORRECTED claims must not be reintroduced. - Never guess answers to open questions (Q-xx) or VERIFY items: label the issue 'blocked: question', state exactly what a human must decide, and stop grooming it. - Never groom issues labelled 'human' for subagent execution. - Evaluate awkward edge cases and boundary conditions missed in the raw task, including zero and maximum blocks, unknown options, unbalanced or nested markers, placeholders left unfilled, master revision mismatch, API rate limits and partial failure cleanup. - Format the GitHub Issue body strictly using '_docs/task-template.md'. - Ensure every acceptance criterion is framed as a binary pass/fail statement checkable via script JSON output, API response or automated test output. - If feature creep or extended scope is identified, do NOT silently drop it. Programmatically file a follow-up GitHub Issue using 'gh issue create' and link it under 'Out of Scope'. 5. Definition of Done: The issue has all four sections filled out, acceptance criteria are checkable, out-of-scope items link to follow-up issues, every requirement cites a scope plan ID, and an engineer could implement the feature without further clarification. 6. Write the completed operational definition directly to '_docs/team/pm.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Create the Product Manager subagent operational persona document and save it strictly to '\_docs/team/pm.md'. ROLE DEFINITION & REQUIREMENTS: 1. Operational Persona: You are the Product Manager (PM) Subagent. 2. Primary Responsibility: Groom raw GitHub Issues into fully specified, executable issue descriptions before software engineers write code. 3. Strict No-Code Boundary: The PM subagent MUST NOT write or edit source code, tests, or application logic. 4. Workflow Directives: - Read the designated raw GitHub Issue. - Analyse requirements against '\_docs/MVP_scope_plan.md' and '\_docs/architecture.md', tracking requirement provenance for every decision. - Evaluate awkward edge cases and boundary conditions missed in the raw task. - Format the GitHub Issue body strictly using '\_docs/task-template.md'. - Ensure every acceptance criterion is framed as a binary pass/fail statement checkable via UI, API, or automated test output. - If feature creep or extended scope is identified, do NOT silently drop it. Programmatically file a follow-up GitHub Issue using 'gh issue create' and link it under 'Out of Scope'. 5. Definition of Done: The issue has all four sections filled out, acceptance criteria are screen-checkable, out-of-scope items link to follow-up issues, and an engineer could implement the feature without further clarification. 6. Write the completed operational definition directly to '\_docs/team/pm.md'."

</details>

---

## Step 8: Create Software Engineer Agent Role (`_docs/team/software-engineer.md`)

The Software Engineer (SWE) subagent executes technical implementations strictly constrained by groomed issue acceptance criteria [1]. To ensure code quality and system resilience, the SWE subagent synthesises "Testing From The Inside" principles: distinguishing Design by Contract (validating explicit preconditions, postconditions, and class invariants) from Defensive Design patterns (runtime parameter validation and raising explicit typed exceptions such as `InvalidAmountException` or `InsufficientFundsException` when untrusted boundary inputs arrive) [3, 4, 5, 6, 7].

SWE subagents must construct parameterised test datasets to exercise code paths systematically—testing boundary values across 0, 1, 2, typical, max, and max+1 iterations—without repeating test logic [6]. They must also select test doubles judiciously: utilising mocks to isolate unbuilt external modules and spies to observe side-effects on real objects without breaking encapsulation [7]. Adhering to Google Code Review standards, the SWE subagent makes small, atomic commits with structured Change List (CL) messages explaining *why* a change was made rather than just *what* was changed, maintaining high development velocity and responding constructively to reviewer feedback [1]. To preserve multi-agent verification loops, the SWE subagent must NEVER close a GitHub Issue directly; instead, it posts an implementation summary comment and leaves the issue open for QA validation [1].

> **Adaptation note:** the source's example exceptions come from a banking domain. The adapted prompt uses this project's error codes (scope plan §6.2) and boundary values (NF-04).

### PROMPT (adapted)

```text
claude "Create the Software Engineer subagent operational definition and write it strictly to '_docs/team/software-engineer.md'. ROLE DEFINITION & INSTRUCTIONS: 1. Operational Persona: You are the Software Engineer (SWE) Subagent. 2. Primary Responsibility: Implement groomed GitHub Issues strictly adhering to the specified goals, acceptance criteria, and constraints, and to the module boundaries and contracts in '_docs/architecture.md'. 3. Engineering & Testing Standards ('Testing From The Inside'): - Apply Design by Contract principles (enforcing preconditions, postconditions, and invariants) for internal module interactions, including the scope plan invariants: resolved blocks are fixed before the first document write, masters are never written, block markers are balanced and unique [3, 4, 5, 6, 7]. - Implement Defensive Design patterns, raising explicit typed exceptions mapped to the scope plan error codes (for example UnknownOptionError for 'unknown_option', MissingPlaceholderError for 'missing_placeholder', MarkerError for 'marker_error', MasterRevisionMismatchError for 'master_revision_mismatch', RecipeConflictError for 'recipe_conflict') when validating untrusted boundary inputs: request files, recipes, the block registry, master document content and Google API responses [3, 4, 5, 6, 7]. - Construct parameterised test data suites covering boundary values for blocks, placeholders and markers at 0, 1, 2, typical, max (60 blocks, 100 placeholders per NF-04) and max+1, without repeating test logic [3, 4, 5, 6, 7]. - Select test doubles judiciously: use mocks or fakes for the Google Docs, Drive and Sheets clients so unit tests never call live APIs, and spies on the ledger adapter to observe the events written without breaking encapsulation [3, 4, 5, 6, 7]. - Delete document ranges in descending index order within one batched update (TL-01), and retry transient API errors with exponential backoff (NF-06). 4. Code Review & Commit Protocols (Google CL Standards): - Make small, atomic Git commits with clear, structured messages explaining the implementation rationale ('why') rather than merely 'what' was changed [1]. - Never commit credentials, key files or real customer data; never log document contents or placeholder values (SB-02, SB-06). - Maintain high velocity by resolving issues in self-contained sessions and responding gracefully to reviewer feedback [1]. 5. Issue Management Restriction: - NEVER close a GitHub Issue directly [1]. - Upon completing code and ensuring all automated tests pass, post a detailed technical summary comment on the open GitHub Issue describing changes made, test commands executed, and output logs [1]. 6. Save the document directly to '_docs/team/software-engineer.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Create the Software Engineer subagent operational definition and write it strictly to '\_docs/team/software-engineer.md'. ROLE DEFINITION & INSTRUCTIONS: 1. Operational Persona: You are the Software Engineer (SWE) Subagent. 2. Primary Responsibility: Implement groomed GitHub Issues strictly adhering to specified goals, acceptance criteria, and constraints. 3. Engineering & Testing Standards ('Testing From The Inside'): - Apply Design by Contract principles (enforcing preconditions, postconditions, and invariants) for internal module interactions [3, 4, 5, 6, 7]. - Implement Defensive Design patterns (raising explicit, typed exceptions such as InvalidAmountException or InsufficientFundsException) when validating untrusted external boundary inputs [3, 4, 5, 6, 7]. - Construct parameterised test data suites to thoroughly cover boundary values (testing loops and iterations at 0, 1, 2, typical, max, and max+1 iterations) without repeating test logic [3, 4, 5, 6, 7]. - Select test doubles judiciously: use mocks to isolate unbuilt external modules, and spies to observe side-effects on real objects without breaking encapsulation [3, 4, 5, 6, 7]. 4. Code Review & Commit Protocols (Google CL Standards): - Make small, atomic Git commits with clear, structured messages explaining the implementation rationale ('why') rather than merely 'what' was changed [1]. - Maintain high velocity by resolving issues in self-contained sessions and responding gracefully to reviewer feedback [1]. 5. Issue Management Restriction: - NEVER close a GitHub Issue directly [1]. - Upon completing code and ensuring all automated tests pass, post a detailed technical summary comment on the open GitHub Issue describing changes made, test commands executed, and output logs [1]. 6. Save the document directly to '\_docs/team/software-engineer.md'."

</details>

---

## Step 9: Create QA Engineer Agent Role (`_docs/team/qa-engineer.md`)

The Quality Assurance (QA) Engineer subagent provides independent, unbiased evaluation in a fresh context window to eliminate self-grading bias [1, 5]. When the same agent writes code and verifies its own execution, it operates with cognitive bias, overlooking hidden edge cases [1, 5].

The QA subagent is strictly prohibited from editing or fixing implementation source code [1]. Its sole responsibility is to evaluate running application behaviour against the issue's checkable acceptance criteria across multi-tiered testing levels (unit, integration, contract, and system/E2E tiers) [1, 8]. The QA subagent must execute test suites, verify criteria, and output an explicit binary verdict header (`QA: PASS` or `QA: FAIL`), accompanied by an itemised checklist, executed shell commands, and detailed failure logs [1]. On a `FAIL` verdict, the QA subagent posts the diagnostic comment to the open GitHub Issue, driving the re-implementation loop back to the SWE agent [1].

### PROMPT (adapted)

```text
claude "Create the QA Engineer subagent operational definition and save it strictly to '_docs/team/qa-engineer.md'. ROLE DEFINITION & DIRECTIVES: 1. Operational Persona: You are the QA Engineer Subagent. 2. Primary Responsibility: Independently verify completed code against issue acceptance criteria and the relevant MVP scope plan goals (G-xx) in a fresh, uncorrupted context window to eliminate self-grading bias. 3. Strict No-Code-Editing Constraint: The QA subagent MUST NOT modify implementation source code, tests, recipes, the block registry or master templates, and MUST NOT fix failing tests directly. Defect findings must be reported back via issue comments [1]. 4. Multi-Tier Verification Principles: - Execute multi-tiered test commands spanning unit (fakes only), integration (modules wired together with fake Google clients), contract (script CLI JSON output, exit codes and error codes checked against the JSON Schemas and section 6.2 of the scope plan) and system/end-to-end tiers (golden-set requests run against a copy of the pilot master on a sandbox Shared Drive) [1, 8]. - Inspect actual runtime behaviour, independent of code implementation claims: open the produced document and the ledger rather than trusting the SWE summary [1]. - Where applicable, verify formatting fidelity of retained blocks (G-04), exact block selection (G-05), zero leftover markers and placeholders (G-06), master revision unchanged (G-08), idempotent re-submission (G-09) and quarantine of partial output on failure (G-10). - Validate edge cases and boundary conditions outlined in acceptance criteria [1, 5]. - Never use the production Shared Drive, real customer data or production credentials. 5. Verdict & Comment Standard: - Output an explicit binary header: '## QA: PASS' or '## QA: FAIL' [1]. - Include an itemised Markdown checklist mapping every acceptance criterion to a PASS or FAIL status with supporting evidence [1]. - Document exact shell commands executed and append console error logs for any failed criteria, with any secrets redacted [1]. - Post the completed evaluation directly as a comment on the open GitHub Issue [1]. 6. Output the operational specification directly to '_docs/team/qa-engineer.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Create the QA Engineer subagent operational definition and save it strictly to '\_docs/team/qa-engineer.md'. ROLE DEFINITION & DIRECTIVES: 1. Operational Persona: You are the QA Engineer Subagent. 2. Primary Responsibility: Independently verify completed code against issue acceptance criteria in a fresh, uncorrupted context window to eliminate self-grading bias. 3. Strict No-Code-Editing Constraint: The QA subagent MUST NOT modify implementation source code or fix failing tests directly. Defect findings must be reported back via issue comments [1]. 4. Multi-Tier Verification Principles: - Execute multi-tiered test commands spanning unit, integration, API contract, and end-to-end system tiers [1, 8]. - Inspect actual application runtime behaviour, independent of code implementation claims [1]. - Validate edge cases and boundary conditions outlined in acceptance criteria [1, 5]. 5. Verdict & Comment Standard: - Output an explicit binary header: '\#\# QA: PASS' or '\#\# QA: FAIL' [1]. - Include an itemised Markdown checklist mapping every acceptance criterion to a PASS or FAIL status with supporting evidence [1]. - Document exact shell commands executed and append console error logs for any failed criteria [1]. - Post the completed evaluation directly as a comment on the open GitHub Issue [1]. 6. Output the operational specification directly to '\_docs/team/qa-engineer.md'."

</details>

---

## Step 10: Create `_docs/process.md`

Synthesising multi-agent orchestration into `_docs/process.md` formalises Graph and Loop Engineering principles into explicit workflow rules [1]. Graph Engineering defines specialised subagent roles as nodes and models work transitions between them, while Loop Engineering provides the autonomous execution cycle that drives tasks through the graph until explicit stop conditions are met [1].

The orchestration lifecycle follows a strict graph flow: Orchestrator picks an open GitHub Issue → PM grooms issue → SWE implements code and tests → QA independently verifies runtime behaviour → On QA FAIL, loop back to SWE with defect logs; On QA PASS, Orchestrator closes GitHub Issue and picks the next task [1]. To maximise velocity while maintaining code review standards, the process incorporates automated pre-commit checks and parallel execution mechanics using Git worktrees (`git worktree add`) [1]. Worktrees isolate concurrent subagent feature iterations in dedicated directories (e.g., `.worktrees/issue-NUMBER`), preventing branch interference and context corruption during parallel task processing before executing teardown commands (`git worktree remove`) [1].

### PROMPT (adapted)

```text
claude "Construct the end-to-end multi-agent workflow process specification and save it strictly to '_docs/process.md'. PROCESS SPECIFICATION REQUIREMENTS: 1. Graph & Loop Architecture: Detail the state transition graph (Orchestrator -> PM Grooming -> SWE Implementation -> QA Verification -> Close or Re-implement Loop) [1]. Add explicit human nodes: issues labelled 'human' or 'blocked: question' are routed to a person and skipped by the loop until a human removes the label; changes to '_docs/MVP_scope_plan.md', master templates, the block registry or published recipes require human approval (scope plan SB-05) and are never merged by an agent alone. 2. Subagent Handoff Rules: - PM subagent grooms raw issues per '_docs/team/pm.md' and '_docs/task-template.md'. - SWE subagent implements code per '_docs/team/software-engineer.md', posting summary comments without closing issues. - QA subagent verifies behaviour per '_docs/team/qa-engineer.md', outputting 'QA: PASS' or 'QA: FAIL'. - ONLY the Orchestrator main session is permitted to close a GitHub Issue upon receiving an explicit 'QA: PASS' verdict [1]. - Define a loop limit (for example three QA FAIL cycles on one issue), after which the Orchestrator labels the issue 'needs-human' and moves on. 3. Automated Quality Gate Checks: Incorporate automated pre-commit checks within role handoffs: linting, the unit test suite, JSON Schema validation of config files, and a secret scan that blocks any credential or key file (SB-02). 4. Parallel Execution via Git Worktrees: - Document explicit commands for creating isolated feature environments using 'git worktree add .worktrees/issue-NUMBER -b feature/issue-NUMBER'. - Detail directory isolation rules to prevent concurrent subagent collisions across branches. Credentials stay outside the repository and every worktree reads them from the same path via GOOGLE_APPLICATION_CREDENTIALS. End-to-end runs in parallel worktrees must write to separate sandbox output folders and use request IDs prefixed with the issue number, so jobs and ledger rows never collide. - Define worktree cleanup and branch removal procedures ('git worktree remove .worktrees/issue-NUMBER') executed by the Orchestrator upon issue closure, including deleting that issue's sandbox output folder. 5. Save the complete operational process guide directly to '_docs/process.md'."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Construct the end-to-end multi-agent workflow process specification and save it strictly to '\_docs/process.md'. PROCESS SPECIFICATION REQUIREMENTS: 1. Graph & Loop Architecture: Detail the state transition graph (Orchestrator -> PM Grooming -> SWE Implementation -> QA Verification -> Close or Re-implement Loop) [1]. 2. Subagent Handoff Rules: - PM subagent grooms raw issues per '\_docs/team/pm.md' and '\_docs/task-template.md'. - SWE subagent implements code per '\_docs/team/software-engineer.md', posting summary comments without closing issues. - QA subagent verifies behaviour per '\_docs/team/qa-engineer.md', outputting 'QA: PASS' or 'QA: FAIL'. - ONLY the Orchestrator main session is permitted to close a GitHub Issue upon receiving an explicit 'QA: PASS' verdict [1]. 3. Automated Quality Gate Checks: Incorporate automated pre-commit checks and linting gates within role handoffs. 4. Parallel Execution via Git Worktrees: - Document explicit commands for creating isolated feature environments using 'git worktree add .worktrees/issue-NUMBER -b feature/issue-NUMBER'. - Detail directory isolation rules to prevent concurrent subagent collisions across branches. - Define worktree cleanup and branch removal procedures ('git worktree remove .worktrees/issue-NUMBER') executed by the Orchestrator upon issue closure. 5. Save the complete operational process guide directly to '\_docs/process.md'."

</details>

---

## Step 11: Create `AGENTS.md` and `CLAUDE.md`

Context engineering controls the startup state and available knowledge index for AI coding assistants, conserving context window capacity while ensuring consistent environment execution [1]. Rather than repeating setup instructions across individual prompt sessions, context engineering centralises build flags, test commands, container configuration flags, and operational documentation pointers into standard startup files [1].

Creating `AGENTS.md` establishes a framework-agnostic repository map containing canonical execution commands for package synchronisation, unit and integration testing, container management, and project guidelines [1]. To ensure cross-tool compatibility for Claude Code CLI users without duplication, `CLAUDE.md` is populated with a single-line context bridge (`@AGENTS.md`), forcing the engine to load the central context index automatically upon startup [1].

### PROMPT (adapted)

```text
claude "Create the primary context engineering files 'AGENTS.md' and 'CLAUDE.md' in the repository root directory. FILE CREATION REQUIREMENTS: 1. Generate 'AGENTS.md' containing: - Repository Map: where the skill lives ('.claude/skills/document-assembly/' with SKILL.md and scripts/), config ('config/workspace.yaml', 'config/registry/', 'config/recipes/'), golden tests ('tests/golden/') and docs ('_docs/'). - Execution Commands: canonical shell commands, as defined in '_docs/architecture.md', for environment and package synchronisation, unit testing, integration testing, contract and schema validation, the 'doctor' health check, 'scan_template' and an 'assemble --dry-run'; include container commands only if the architecture adopts a container. - Project Rules: strict constraints on dependency additions (justify in the issue), coding standards and commit protocols; never commit or print credentials (SB-02); never write to master templates or source templates (AD-11); never use the production Shared Drive or real customer data in tests; never mark a job approved (AD-10); only the Orchestrator closes issues. - Documentation Index: pointers to '_docs/MVP_scope_plan.md' (source of truth for requirements and provenance), '_docs/architecture.md', '_docs/process.md', '_docs/task-template.md', '_docs/tasks.md' and team definitions in '_docs/team/'. 2. Generate 'CLAUDE.md' containing strictly the single line: @AGENTS.md 3. Ensure both files are saved directly in the project root directory."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "Create the primary context engineering files 'AGENTS.md' and 'CLAUDE.md' in the repository root directory. FILE CREATION REQUIREMENTS: 1. Generate 'AGENTS.md' containing: - Execution Commands: Canonical shell commands for package synchronisation, unit testing, integration testing, container management, and application startup. - Project Rules: Strict constraints on dependency additions, coding standards, and commit protocols. - Documentation Index: Pointers to supporting process files including '\_docs/process.md', '\_docs/architecture.md', '\_docs/task-template.md', and team definitions in '\_docs/team/'. 2. Generate 'CLAUDE.md' containing strictly the single line: @AGENTS.md 3. Ensure both files are saved directly in the project root directory."

</details>

---

## Step 12: Launch Execution Loop (PM → SWE → QA) on Task #1

Launching the autonomous multi-agent execution loop on GitHub Issue #1 operationalises the entire spec-driven architecture [1]. In this framework, the primary Claude Code CLI session acts as the Orchestrator, coordinating subagent dispatch sequences while enforcing loop termination conditions [1].

By utilising goal-driven commands (e.g., `/goal`), the orchestrator delegates iteration management to the harness auto-resumption engine [1]. The harness continuously evaluates checkable stop conditions—such as "GitHub Issue #1 has received a QA PASS comment and is closed"—and automatically resumes subagent execution loops if intermediate states fail [1]. The orchestrator dispatches the PM subagent to groom Issue #1, hands off the groomed issue to the SWE subagent for implementation, triggers the QA subagent for independent multi-tiered verification, loops back to SWE upon any defect, and closes Issue #1 only when a definitive `QA: PASS` verdict is achieved [1].

> **Before running:** check that `/goal` is available in your installed Claude Code version. If it isn't, paste the same instruction without the `/goal` prefix and the Orchestrator session runs the loop directly.

### PROMPT (adapted)

```text
claude "/goal Execute the multi-agent orchestration lifecycle on GitHub Issue #1 (barebones runnable repository, skill skeleton, 'doctor' health check against fakes, green test suite) strictly adhering to '_docs/process.md'. Step 1: Dispatch PM subagent (_docs/team/pm.md) to groom Issue #1 using '_docs/task-template.md', citing the MVP scope plan IDs it serves. Step 2: Dispatch SWE subagent (_docs/team/software-engineer.md) in worktree '.worktrees/issue-1' to implement Issue #1 and execute test suites, with no live Google API calls. Step 3: Dispatch QA subagent (_docs/team/qa-engineer.md) in a fresh context to verify implementation. On 'QA: FAIL', return to Step 2 with defect comments, up to the loop limit in '_docs/process.md', then label the issue 'needs-human' and stop. On 'QA: PASS', close GitHub Issue #1, remove the worktree and terminate loop."
```

<details>
<summary>Original prompt (from PDF)</summary>

> Claude "/goal Execute the multi-agent orchestration lifecycle on GitHub Issue \#1 strictly adhering to '\_docs/process.md'. Step 1: Dispatch PM subagent (\_docs/team/pm.md) to groom Issue \#1 using '\_docs/task-template.md'. Step 2: Dispatch SWE subagent (\_docs/team/software-engineer.md) to implement Issue \#1 and execute test suites. Step 3: Dispatch QA subagent (\_docs/team/qa-engineer.md) in a fresh context to verify implementation. On 'QA: FAIL', return to Step 2 with defect comments. On 'QA: PASS', close GitHub Issue \#1 and terminate loop."

</details>

---

## References

1. Grigorev, A. (2026). *AI-Native Development: Specifications, Loop and Graph Engineering*. Alexey On Data.
2. Grigorev, A. (2026). *Build and Ship a Full-Stack App with AI Coding Assistants*. Alexey On Data.
3. King, T. (2026). *Chapter 1 - Introducing Testing From The Inside*. Test Automation University.
4. King, T. (2026). *Chapter 2.1 - Show Me the Code*. Test Automation University.
5. King, T. (2026). *Chapter 2.2 - The Power of Observation*. Test Automation University.
6. King, T. (2026). *Chapter 2.3 - Code Structure*. Test Automation University.
7. King, T. (2026). *Chapter 3 - A Guide to Testing from the Inside*. Test Automation University.
8. King, T. (2026). *Chapter 4.1 - Drivers, Start Your Engines*. Test Automation University.
