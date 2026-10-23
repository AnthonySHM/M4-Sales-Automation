# AGENTS.md — Repository Context Index

> Loaded automatically by Claude Code and compatible AI coding agents.
> All subagents must read this file at the start of every session.

---

## Repository Map

```
.
├── .claude/skills/document-assembly/
│   ├── SKILL.md                          # Claude Code skill entry point
│   └── scripts/
│       ├── doctor.py                     # Health check
│       ├── scan_template.py              # Template marker validation
│       ├── validate_request.py           # Request + recipe validation
│       ├── assemble.py                   # Core job runner
│       └── review.py                     # Approve / reject output
├── config/
│   ├── workspace.yaml                    # Drive IDs, folder IDs, ledger ref, workspace_id
│   ├── registry/<family_key>.json        # Block registry per document family
│   └── recipes/<family_key>_v<N>.json    # Assembly recipe per family + version
├── schemas/
│   ├── request.schema.json
│   ├── recipe.schema.json
│   ├── registry.schema.json
│   ├── job.schema.json
│   └── event.schema.json
├── tests/
│   ├── unit/                             # Fakes only — no live API calls
│   ├── integration/                      # Fake Google clients injected
│   ├── contract/                         # CLI output vs JSON Schemas
│   └── golden/                           # E2E on sandbox Shared Drive only
├── _docs/                                # Project documentation (source of truth)
└── .worktrees/                           # Git worktrees for parallel agent work (gitignored)
```

---

## Execution Commands

### Environment setup (once per machine)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export GOOGLE_APPLICATION_CREDENTIALS=/path/outside/repo/sa.key.json
# Key file must NEVER be inside the repository.
```

### Health check
```bash
python .claude/skills/document-assembly/scripts/doctor.py
# Expected: {"status": "ok", ...}
```

### Unit tests
```bash
pytest tests/unit/ -v
```

### Integration tests
```bash
pytest tests/integration/ -v
```

### Contract / schema validation
```bash
pytest tests/contract/ -v
```

### E2E golden-set tests (sandbox Drive only — never production)
```bash
pytest tests/golden/ -v
```

### Validate all config files against schemas
```bash
python scripts/validate_schemas.py
```

### Dry-run assembly (no Drive writes)
```bash
python .claude/skills/document-assembly/scripts/assemble.py \
  --request tests/golden/requests/sample_request.json \
  --dry-run
```

### Scan a template for marker issues
```bash
python .claude/skills/document-assembly/scripts/scan_template.py \
  --file-id <GOOGLE_DOC_ID> \
  --registry config/registry/<family_key>.json
```

---

## Project Rules

### Security (non-negotiable)
- **Never commit credentials.** No `*.key.json`, `*.pem`, `credentials*.json`, or `.env` files. The `.gitignore` enforces this; the pre-commit secret scan enforces it again. (SB-02)
- **Never write to master templates.** Jobs only copy masters. Only the Content Curator (R-03) may edit masters. (AD-11)
- **Never use the production Shared Drive in tests.** Use the sandbox Drive only. (SB-05)
- **Never log document content, placeholder values, or PII.** Logs go to stderr as structured JSON. (SB-06)
- **Never close a GitHub Issue directly.** Only the Orchestrator session closes issues, after `QA: PASS`.

### Code standards
- Python 3.11+. Follow the architecture in `_docs/architecture.md`.
- All new dependencies must be justified in the issue before adding to `requirements.txt`.
- Small, atomic commits explaining *why*, not just *what*. Follow Google CL standards.
- All commits pass pre-commit hooks: linting, unit tests, schema validation, secret scan.
- Never skip hooks with `--no-verify` without explicit Orchestrator instruction.

### Agent roles
- PM grooms issues (`_docs/team/pm.md`).
- SWE implements (`_docs/team/software-engineer.md`).
- QA verifies in a fresh context (`_docs/team/qa-engineer.md`).
- See `_docs/process.md` for the full orchestration lifecycle.

---

## Documentation Index

| File | Purpose |
|---|---|
| `_docs/MVP_scope_plan.md` | **Source of truth** for all requirements, provenance tags (USER/AGREED/INFERRED/ASSUMED/CORRECTED/VERIFY), open questions (Q-xx), architectural decisions (AD-xx), goals (G-xx), non-functional bounds (NF-xx), security boundaries (SB-xx), technical limits (TL-xx) |
| `_docs/architecture.md` | Tech stack, repository layout, script CLI contracts, JSON schemas, ledger adapter interface, Google API usage, testing strategy |
| `_docs/tasks.md` | Full task backlog ordered by delivery phase P0–P5 |
| `_docs/task-template.md` | Mandatory four-section template for grooming GitHub Issues |
| `_docs/process.md` | Multi-agent orchestration lifecycle, handoff rules, worktree management, loop limits |
| `_docs/team/pm.md` | PM subagent operational definition |
| `_docs/team/software-engineer.md` | SWE subagent operational definition |
| `_docs/team/qa-engineer.md` | QA subagent operational definition |
