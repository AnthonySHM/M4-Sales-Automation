# Human Tasks Progress

This file tracks progress on all human-required tasks. At the start of any new session, read this file to know exactly where to resume.

---

## Current Status: Waiting on admin email response (Issue #2 blocker)

---

## Summary of all human tasks

| Issue | Phase | Title | Status |
|---|---|---|---|
| #2 | P0 | Create Google Cloud project and service account | ❌ Blocked |
| #3 | P0 | Provision Shared Drive and folder structure | ⏳ Waiting on #2 |
| #4 | P0 | Confirm Claude Team plan seats include Claude Code | ✅ Closed |
| #7 | P1 | Decompose pilot contract family into master template | ⏳ Waiting on #3 |
| #10 | P2 | Author assembly recipe for pilot family | ⏳ Waiting on #7, #9 |
| #17 | P4 | Second teammate onboarding test | ⏳ Waiting on #16 |
| #19 | P5 | Pilot measurement: manual vs automated time | ⏳ Waiting on #17 |
| #33 | P6 | Set up Google Cloud infrastructure (web UI) | ⏳ Waiting on #2 |
| #43 | P10 | Web UI pilot: ≥5 contracts via browser | ⏳ Waiting on #31, #19 |

---

## Issue #2 — Create Google Cloud project and service account

| Step | Status | Detail |
|---|---|---|
| Open Google Cloud Console | ✅ Done | |
| Identify existing project | ✅ Done | Project: **Sales Automation** · Project ID: `second-modem-500910-d1` |
| Enable APIs | ✅ Done | Google Drive API, Google Docs API, Google Sheets API — all enabled |
| Create service account | ✅ Done | Name: `m4-document-assembly` · Project: `second-modem-500910-d1` |
| Download JSON key | ❌ Blocked | Org policy blocks service account key creation |
| Distribute key to team | ⏳ Pending step above | |

### Blocker
The organisation has a policy that prevents service account key creation. An email has been sent to the Google Workspace admin requesting either:
- An exemption for `m4-document-assembly` to create a JSON key, or
- The admin creates the key and shares it securely

### Fallback options (if admin does not grant exemption)
- **Option B:** Each teammate authenticates with their own Google identity via `gcloud auth application-default login` — no key file needed. Edits attributed to individual identities (resolves Q-04).
- **Option C:** Re-create the project under a personal Gmail account (no org policies apply).

### What is needed to mark this complete
- The JSON key file distributed to all teammates, stored at a local path outside the repo (e.g. `~/.config/m4-sales/sa.key.json`)
- Each teammate sets: `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/m4-sales/sa.key.json`
- OR a decision is made to use Option B or C above and this file is updated accordingly

---

## Issue #3 — Provision Shared Drive and folder structure

**Waiting on:** Issue #2

| Step | Status | Detail |
|---|---|---|
| Create Shared Drive | ⏳ Not started | |
| Create folders: masters/, review/, approved/, quarantine/ | ⏳ Not started | |
| Grant service account access to Shared Drive | ⏳ Not started | |
| Create ledger Google Sheet on Shared Drive | ⏳ Not started | |
| Fill IDs into config/workspace.yaml | ⏳ Not started | |

### What is needed to mark this complete
Fill the following into `config/workspace.yaml`:

| Field | Value needed |
|---|---|
| `shared_drive_id` | ID of the Shared Drive |
| `folders.masters` | Folder ID |
| `folders.review` | Folder ID |
| `folders.approved` | Folder ID |
| `folders.quarantine` | Folder ID |
| `ledger.spreadsheet_id` | Google Sheet ID |

---

## Issue #4 — Confirm Claude Team plan seats include Claude Code

**Status: ✅ CLOSED**

Only the developer needs Claude Pro. Teammates running jobs need only Python and Google credentials — no Claude Team plan seats required.

---

## Issue #7 — Decompose pilot contract family into master template

**Waiting on:** Issue #3 (Shared Drive must exist) + Issue #8 (scan_template.py — already closed ✅)

| Step | Status | Detail |
|---|---|---|
| Resolve Q-01 — identify pilot contract family | ✅ Done | **MSS SOW — Resell + Refer channel**. Posted as comment on Issue #7. |
| Analyse contract — mark optional sections | ✅ Done | 21 blocks identified (see block list below) |
| Analyse contract — mark variable fields | ✅ Done | 16 placeholders identified (see placeholder list below) |
| Assign block_ids to all optional sections | ✅ Done | See `config/registry/mss_sow.json` |
| Assign PLACEHOLDER_KEY names to all variable fields | ✅ Done | See `config/recipes/mss_sow_v1.json` placeholder_map |
| Create master Google Doc in masters/ folder | ⏳ Not started | Waiting on Issue #3 |
| Add [[BLOCK:id]] / [[/BLOCK:id]] markers to doc | ⏳ Not started | Use block list below as the guide |
| Add {{PLACEHOLDER_KEY}} tokens to doc | ⏳ Not started | Body only — not in headers, footers, or footnotes |
| Run scan_template.py — confirm 0 issues | ⏳ Not started | `python .claude/skills/document-assembly/scripts/scan_template.py --file-id <id>` |
| Update config/workspace.yaml pilot_family section | ⏳ Not started | Set `pilot_family.master_template_id` and `pilot_family.key` via PR |

### Q-01 Resolution
- **Pilot family:** MSS SOW (Managed Security Services Statement of Work)
- **Channel scope:** Resell + Refer only (Direct SOW is a separate family — post-pilot)
- **Source files:** `vf` (version final) files in `Contracts/1 Master Temps & Tool/MSS SOW Est Temps/`
- **family_key:** `mss_sow`

### Block list (21 blocks) — use this when marking up the Google Doc

| block_id | What it is | Included for |
|---|---|---|
| `partner_logo` | Partner logo on cover page | Resell channel only |
| `service_desc_elite` | Elite service description paragraph | tier = elite |
| `service_desc_enterprise` | Enterprise service description paragraph | tier = enterprise |
| `service_desc_premium` | Premium service description paragraph | tier = premium |
| `service_desc_strategic` | Strategic (Stratus) service description paragraph | tier = strategic |
| `mdr_ndr_led` | MDR section — leads with NDR | Elite, Premium |
| `mdr_cloud_led` | MDR section — leads with Cloud Services | Strategic |
| `mdr_enterprise` | MDR/SecurityBox section for Enterprise | Enterprise |
| `bench_ndr` | Analyst Bench — NDR subsection | Elite, Premium, Enterprise |
| `bench_cloud_identity` | Analyst Bench — Cloud and Identity subsection | Elite, Enterprise, Strategic |
| `isensor` | NDR iSensor (hardware/virtual) paragraph | Elite, Premium, Enterprise |
| `addon_siem` | SIEM Service add-on section | Optional |
| `addon_firewall_compliance` | Firewall Rule Compliance Monitoring add-on | Optional |
| `addon_storage` | Additional Data Storage add-on | Optional |
| `addon_endpoint_patching` | Endpoint Patching Assessment add-on | Optional |
| `addon_sentinelone` | SentinelOne XDR Licensing section | Optional |
| `fees_table_elite` | Pricing table with Elite SKU (M4ELIT1002) | tier = elite |
| `fees_table_enterprise` | Pricing table with Enterprise SKU (M4ENTN1001) | tier = enterprise |
| `fees_table_premium` | Pricing table with Premium SKU | tier = premium |
| `fees_table_strategic` | Pricing table with Strategic SKU | tier = strategic |
| `slo_section` | Service Level Objectives table | Optional (negotiated deals) |

### Placeholder list (16 placeholders)

| PLACEHOLDER_KEY | What it is |
|---|---|
| `{{CUSTOMER_NAME}}` | Customer company name |
| `{{CUSTOMER_LOGO}}` | Customer logo (on cover) |
| `{{CUSTOMER_CONTACT_NAME}}` | Customer signatory name |
| `{{CUSTOMER_CONTACT_TITLE}}` | Customer signatory title |
| `{{ACCOUNT_MANAGER_NAME}}` | M4 Account Manager name |
| `{{SOW_DATE}}` | Date on cover page |
| `{{QUOTE_NUMBER}}` | Quote number (M4RR-10xx for Resell, M4RF-10xx for Refer) |
| `{{REVISION_NUMBER}}` | Revision number or "Original" |
| `{{MSA_DATE}}` | Date MSA was signed |
| `{{ORDER_START_DATE}}` | Service start date |
| `{{HOT_STORAGE_MONTHS}}` | Hot storage months (add-on storage block) |
| `{{COLD_STORAGE_MONTHS}}` | Cold storage months (add-on storage block) |
| `{{POC_FEE_MONTHLY}}` | Monthly fee during POC period |
| `{{TERM_FEE_MONTHLY}}` | Monthly fee during term |
| `{{REMAINDER_FEE_MONTHLY}}` | Monthly fee for remainder |
| `{{MIN_ENDPOINT_COUNT}}` | Minimum endpoint count (60 for Elite, 120 for Enterprise) |

### Draft config files created (ready for review)
- `config/registry/mss_sow.json` — block registry ✅
- `config/recipes/mss_sow_v1.json` — assembly recipe (status: draft) ✅

### Marker format rules (from Issue #7)
- Opening tag: `[[BLOCK:block_id]]` — on its own paragraph
- Closing tag: `[[/BLOCK:block_id]]` — on its own paragraph
- `block_id` must match: `^[a-z0-9_]{3,64}$`
- Blocks must be balanced (every open has exactly one close)
- Blocks must not be nested inside other blocks
- Each block must wrap whole paragraphs or whole tables — never partial rows or mid-sentence
- Placeholder format: `{{PLACEHOLDER_KEY}}` where key matches `^[A-Z0-9_]+$`
- No markers or placeholders in headers, footers, or footnotes (Q-07 unresolved — workaround: fill footer manually before review)

---

## Issue #10 — Author assembly recipe for pilot family

**Waiting on:** Issue #7 (master template complete) + Issue #9 (block registry JSON — automated task)

| Step | Status | Detail |
|---|---|---|
| Resolve Q-02 — confirm structured JSON form as input method | ⏳ Not started | Post confirmation as comment on Issue #10 |
| Draft recipe mapping options → block include/exclude lists | ⏳ Not started | Every option value must map to a known block set |
| Ensure every [[BLOCK:id]] in master has a recipe entry | ⏳ Not started | |
| Ensure every {{PLACEHOLDER_KEY}} in master has a placeholder_map entry | ⏳ Not started | |
| Validate recipe against schemas/recipe.schema.json | ⏳ Not started | `python -c "import jsonschema, json; ..."` exits 0 |
| Run validate_request.py against all golden-set profiles | ⏳ Not started | All exit 0 |
| Run pytest tests/contract/ -v | ⏳ Not started | All pass |

### File to create
`config/recipes/<family_key>_v1.json` — replace `<family_key>` with the value from Issue #7.

---

## Issue #17 — Second teammate onboarding test

**Waiting on:** Issue #16 (E2E golden-set tests — automated task)

| Step | Status | Detail |
|---|---|---|
| Teammate clones repo on clean machine | ⏳ Not started | |
| Teammate follows README setup steps | ⏳ Not started | Target: complete in ≤30 min |
| Teammate runs doctor.py — confirm exits 0 | ⏳ Not started | |
| Teammate runs one golden-set job to completion | ⏳ Not started | Job reaches awaiting_review; doc appears in review/ folder |
| Log all friction points as comments on Issue #17 | ⏳ Not started | Any confusion or failure points become follow-up issues |

---

## Issue #19 — Pilot measurement: manual vs automated time

**Waiting on:** Issue #17 (onboarding test complete)

| Step | Status | Detail |
|---|---|---|
| Record manual baseline time per contract | ⏳ Not started | Average hands-on time before automation |
| Assemble ≥5 real contracts using the tool | ⏳ Not started | Each must reach approved/ folder |
| Log hands-on time per job | ⏳ Not started | Submitter prep time + reviewer time + correction cycles |
| Post comparison table as comment on Issue #19 | ⏳ Not started | Automated vs manual, percentage reduction |
| R-02 posts go/no-go decision for second contract family | ⏳ Not started | GO / CONDITIONAL GO / NO GO |

---

## Issue #33 — Set up Google Cloud infrastructure (web UI)

**Waiting on:** Issue #2 (service account must exist first)

| Step | Status | Detail |
|---|---|---|
| Create Cloud Run service | ⏳ Not started | Record service name in config/cloud.yaml |
| Store secrets in Secret Manager | ⏳ Not started | `GOOGLE_CREDENTIALS_JSON`, `SESSION_SECRET_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| Configure Google OAuth consent screen | ⏳ Not started | Resolve Q2-04: internal users only? |
| Store OAuth client ID and secret in Secret Manager | ⏳ Not started | |
| Fill config/cloud.yaml with resource names (no values) | ⏳ Not started | Project ID, Cloud Run service name, secret names, Artifact Registry repo |

### What is needed to mark this complete
`config/cloud.yaml` filled with resource names (never secret values), and all four secrets exist in Secret Manager.

---

## Issue #43 — Web UI pilot: ≥5 contracts via browser

**Waiting on:** Issue #31 (Claude API integration — automated) + Issue #19 (manual baseline)

| Step | Status | Detail |
|---|---|---|
| Non-developer teammates submit ≥5 real contracts via browser | ⏳ Not started | Using deployed Cloud Run URL |
| R-06 Reviewer approves all 5 via browser review UI | ⏳ Not started | |
| Confirm no teammate held a service-account key file | ⏳ Not started | |
| Record hands-on time per contract | ⏳ Not started | Submitter time + reviewer time |
| Log friction points as new GitHub issues | ⏳ Not started | |

---

## What you can do right now (while waiting on admin)

These steps require no Google infrastructure and can be completed immediately:

1. **Resolve Q-01** — decide which contract type is the pilot family. Post the answer as a comment on Issue #7.
2. **Analyse the pilot contract** — go through it and identify every optional section (future blocks) and every variable field (future placeholders).
3. **Draft block IDs and placeholder names** — assign names following the format rules above.
4. **Draft the block registry JSON** (Issue #9 prep) — list all blocks with IDs, labels, kinds, and statuses.
5. **Draft the recipe JSON** (Issue #10 prep) — map customer options to block include/exclude lists.

---

## Next action (resume here)

**Waiting for:** Google Workspace admin to respond to the email about the service account key exemption.

**When admin responds:**
- Exemption granted → download JSON key → complete Issue #2 → move to Issue #3
- Admin refuses → choose Option B (`gcloud auth application-default login`) or Option C (personal Gmail project) → update this file with the chosen path

**After Issue #2 resolved → Issue #3:** Create the Shared Drive and four folders.
