# Document Assembly Skill

Assembles customer contracts from nested Google Drive templates using a declarative recipe and a master template with block markers.

## Scripts

- `scripts/doctor.py` — Health check: verifies credentials, API reachability, Shared Drive membership, and master template accessibility.
- `scripts/scan_template.py` — Validates block markers in a master template Google Doc.
- `scripts/validate_request.py` — Validates an assembly request JSON against the recipe schema.
- `scripts/assemble.py` — Core job runner: copy master → prune blocks → fill placeholders → strip markers → submit for review.

## Usage

```bash
# Health check (run first)
python .claude/skills/document-assembly/scripts/doctor.py

# Dry-run assembly (no Drive writes)
python .claude/skills/document-assembly/scripts/assemble.py \
  --request <request.json> --dry-run

# Full assembly
python .claude/skills/document-assembly/scripts/assemble.py \
  --request <request.json>
```

## Setup

See `AGENTS.md` for environment setup and `_docs/architecture.md` for full CLI contracts.
