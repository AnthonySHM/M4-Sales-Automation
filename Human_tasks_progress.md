# Human Tasks Progress

This file tracks progress on all human-required setup tasks. At the start of any new session, read this file to know exactly where to resume.

---

## Current Status: Waiting on admin email response

---

## Issue #2 — Create Google Cloud project and service account

| Step | Status | Detail |
|---|---|---|
| 1. Open Google Cloud Console | ✅ Done | |
| 2. Identify existing project | ✅ Done | Project: **Sales Automation** · Project ID: `second-modem-500910-d1` |
| 3. Enable APIs | ✅ Done | Google Drive API, Google Docs API, Google Sheets API — all enabled |
| 4. Create service account | ✅ Done | Name: `m4-document-assembly` · Project: `second-modem-500910-d1` |
| 5. Download JSON key | ❌ Blocked | Org policy blocks service account key creation |
| 6. Distribute key to team | ⏳ Pending step 5 | |

### Blocker on step 5
The organisation has a policy that prevents service account key creation. An email has been drafted and sent to the Google Workspace admin requesting either:
- An exemption for `m4-document-assembly` to create a JSON key, or
- The admin creates the key and shares it securely

### Fallback options (if admin does not grant exemption)
- **Option B:** Each teammate authenticates with their own Google identity via `gcloud auth application-default login` — no key file needed. Edits attributed to individual identities (resolves Q-04).
- **Option C:** Re-create the project under a personal Gmail account (no org policies apply).

### What is needed to mark this complete
- The JSON key file (`.json`) distributed to all teammates, stored at a local path outside the repo (e.g. `~/.config/m4-sales/sa.key.json`)
- Each teammate sets: `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/m4-sales/sa.key.json`
- OR a decision is made to use Option B or C above

---

## Issue #3 — Provision Shared Drive and folder structure

| Step | Status | Detail |
|---|---|---|
| Create Shared Drive | ⏳ Not started | Waiting on Issue #2 to be resolved first |
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

| Step | Status | Detail |
|---|---|---|
| Check current seat tier | ⏳ Not started | |
| Confirm Claude Code CLI is included | ⏳ Not started | |

### What is needed to mark this complete
A yes/no answer: does the current Claude Team plan seat tier include Claude Code CLI access for all teammates?

---

## Automated tasks unblocked once human tasks complete

| Automated task | Waiting on |
|---|---|
| Issue #5: doctor.py full implementation | Issue #2 + Issue #3 |
| Issue #7: Decompose pilot contract into master template | Issue #3 + Issue #8 |
| Issue #17: Second teammate onboarding test | Issue #16 + Issue #4 |

---

## Next action (resume here)

**Waiting for:** Google Workspace admin to respond to the email about the service account key exemption.

**When admin responds:**
- If exemption granted → download the JSON key → go to Issue #2 Step 6 (distribute key to team)
- If admin refuses → decide between Option B (`gcloud auth application-default login`) or Option C (personal Gmail project) → update this file with the chosen option

**After Issue #2 is resolved → move to Issue #3, Step 1:** Create the Shared Drive.
