# Human Tasks Progress

This file tracks progress on all human-required tasks. At the start of any new session, read this file to know exactly where to resume.

---

## Current Status: Issue #7 ✅ closed. Issue #9 ✅ closed. Issue #3 ⏳ reopened — blocked on Issue #2 (service account) and Issue #18 (denied-access test). Auth working via custom OAuth client: `GOOGLE_APPLICATION_CREDENTIALS=C:/Users/User/m4-user-credentials.json`. Issue #10 is now unblocked — both dependencies (#7, #9) are closed. Still waiting on admin for Issue #2 service account key.

---

## Summary of all human tasks

| Issue | Phase | Title | Status |
|---|---|---|---|
| #2 | P0 | Create Google Cloud project and service account | ❌ Blocked (key creation blocked by org policy) |
| #3 | P0 | Provision Shared Drive and folder structure | ⏳ Blocked on #2 (service account ACs) and #18 (denied-access test) |
| #4 | P0 | Confirm Claude Team plan seats include Claude Code | ✅ Closed |
| #7 | P1 | Decompose pilot contract family into master template | ✅ Closed |
| #9 | P1 | Block registry JSON for pilot family | ✅ Closed (automated — 21 blocks, all ACs pass) |
| #10 | P2 | Author assembly recipe for pilot family | ✅ Unblocked — ready to start |
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
| Install Google Cloud CLI | ✅ Done | Installed and configured, project `second-modem-500910-d1` selected |
| Set up user auth (Option B) | ✅ Done | Custom OAuth client created (`m4-oauth-client.json`), credentials at `C:/Users/User/m4-user-credentials.json` |
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

**Status: ⏳ OPEN — blocked on Issue #2 (service account ACs) and Issue #18 (denied-access test)**

Using `Mantix4-Sales > M4 Document Assembly` folder in the organisation Google Drive (Option B — gcloud auth, no service account key required for pilot CLI).

| Step | Status | Detail |
|---|---|---|
| Create Shared Drive | ✅ Done | Regular Google Drive folder: `M4 Document Assembly` inside `Mantix4-Sales` |
| Create folders: masters/, review/, approved/, quarantine/ | ✅ Done | All four subfolders created |
| Grant service account access to Shared Drive | ➡️ N/A for pilot | Using Option B (gcloud auth application-default login) instead |
| Create ledger Google Sheet on Shared Drive | ✅ Done | Sheet created in `M4 Document Assembly` |
| Fill IDs into config/workspace.yaml | ✅ Done | All 6 IDs committed to main |

### IDs now in config/workspace.yaml

| Field | ID |
|---|---|
| `shared_drive_id` | `1TOI0xeXN__be3Mb7jB2QCsPWur_9nQWG` |
| `folders.masters` | `1IH_e6zz_n4RiSQw3YspIYRvjrogbc0jX` |
| `folders.review` | `1cjMRpgw3q0qrAmuMCn9CbAqeSwIkVodd` |
| `folders.approved` | `1uH2N9g0Q2kzfwYFN6hJhPtQgUm0438v7` |
| `folders.quarantine` | `1avRkalemhYLBU7tF1WtARSdNtPzyhnVP` |
| `ledger.spreadsheet_id` | `1CjSkWyKtvWM-OW_9X1vubbC857P_SDvLUFheeP2XcwA` |

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
| Create master Google Doc in masters/ folder | ✅ Done | Google Doc ID: `1KdmVNOjEGI3y-16Xx3XLU5SwnXgbuNfUyKSKoF35j9w` |
| Add [[BLOCK:id]] / [[/BLOCK:id]] markers to doc | ✅ Done | Added via `scripts/build_master_template.py`, converted from Word to Google Doc |
| Add {{PLACEHOLDER_KEY}} tokens to doc | ✅ Done | All 16 placeholders present in body (not headers/footers) |
| Run scan_template.py — confirm 0 issues | ✅ Done | 21 markers found, 0 issues. Auth: `GOOGLE_APPLICATION_CREDENTIALS=C:/Users/User/m4-user-credentials.json` |
| Update config/workspace.yaml pilot_family section | ✅ Done | `master_template_id` and `key` committed to main |

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

**✅ Unblocked — Issue #7 and Issue #9 are both closed. Ready to start.**

A draft recipe already exists at `config/recipes/mss_sow_v1.json` from prior work — review and complete it.

| Step | Status | Detail |
|---|---|---|
| Resolve Q-02 — confirm structured JSON form as input method | ⏳ Not started | Post confirmation as comment on Issue #10 |
| Draft recipe mapping options → block include/exclude lists | ⏳ Not started | Every option value must map to a known block set |
| Ensure every [[BLOCK:id]] in master has a recipe entry | ⏳ Not started | |
| Ensure every {{PLACEHOLDER_KEY}} in master has a placeholder_map entry | ⏳ Not started | |
| Validate recipe against schemas/recipe.schema.json | ⏳ Not started | `python -c "import jsonschema, json; ..."` exits 0 |
| Run validate_request.py against all golden-set profiles | ⏳ Not started | All exit 0 |
| Run pytest tests/contract/ -v | ⏳ Not started | All pass |

### File to complete
`config/recipes/mss_sow_v1.json` — draft exists, needs review and completion.

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

## Auth setup (complete — use this on every machine)

Auth uses a custom OAuth client instead of a service account key (org policy blocks key creation).

```bash
# Set this in every terminal session before running any script:
export GOOGLE_APPLICATION_CREDENTIALS="C:/Users/User/m4-user-credentials.json"
```

If credentials expire, re-run the OAuth flow:
```bash
cd "C:/Users/User/Desktop/M4 Sales Automation/M4-Sales-Automation"
source .venv/Scripts/activate
python -c "
import json
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES = ['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/documents','https://www.googleapis.com/auth/spreadsheets']
flow = InstalledAppFlow.from_client_secrets_file('C:/Users/User/m4-oauth-client.json/client_secret_1049228583201-j912uf14r8io0k3lh0onqkr1cso7rb6m.apps.googleusercontent.com.json', SCOPES)
creds = flow.run_local_server(port=0)
import json; open('C:/Users/User/m4-user-credentials.json','w').write(json.dumps({'type':'authorized_user','client_id':creds.client_id,'client_secret':creds.client_secret,'refresh_token':creds.refresh_token}))
print('Done')
"
```

---

## Next action (resume here)

**Issue #10 is unblocked.** Both dependencies (#7 master template, #9 block registry) are closed.

**Your next human task:** Complete the assembly recipe at `config/recipes/mss_sow_v1.json`. A draft already exists — review it, fill in the option → block mappings, and post Q-02 resolution as a comment on Issue #10.

**Still waiting on admin:** Issue #2 service account key (org policy blocker). Issues #3 and #18 remain open until resolved.
