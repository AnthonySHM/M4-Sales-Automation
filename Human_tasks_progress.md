# Human Tasks Progress

This file tracks progress on all human-required tasks. At the start of any new session, read this file to know exactly where to resume.

---

## Current Status (as of 2026-10-30, end of session)

**Issues #2 and #3 are now CLOSED.** Service account key obtained (`C:\Users\User\m4-service-account.json`), Drive folder shared with service account, `doctor.py` exits 0 with all 5 checks passing. The critical path to production is now Issue #33 (Cloud Run infrastructure).

---

## Summary of all human tasks

| Issue | Phase | Title | Status |
|---|---|---|---|
| #2 | P0 | Create Google Cloud project and service account | ✅ Closed (2026-10-30) |
| #3 | P0 | Provision Shared Drive and folder structure | ✅ Closed (2026-10-30) |
| #4 | P0 | Confirm Claude Team plan seats include Claude Code | ✅ Closed |
| #7 | P1 | Decompose pilot contract family into master template | ✅ Closed |
| #9 | P1 | Block registry JSON for pilot family | ✅ Closed |
| #10 | P2 | Author assembly recipe for pilot family | ✅ Closed |
| #17 | P4 | Second teammate onboarding test | ⏳ Ready to start (web UI confirmed working) |
| #19 | P5 | Pilot measurement: manual vs automated time | ⏳ Waiting on #17 |
| #33 | P6 | Set up Google Cloud infrastructure (web UI) | ⏳ Ready to start (unblocked — service account key ready) |
| #35 | P6 | Dockerfile + Cloud Build pipeline | ⏳ Ready to implement (automated — just needs #33 done first to test deploy) |
| #43 | P10 | Web UI pilot: ≥5 contracts via browser | ⏳ Waiting on #33 (Cloud Run deploy) |

---

## Issue #2 — Create Google Cloud project and service account

**Status: ✅ CLOSED (2026-10-30)**

| Step | Status | Detail |
|---|---|---|
| Open Google Cloud Console | ✅ Done | |
| Identify existing project | ✅ Done | Project: **Sales Automation** · Project ID: `second-modem-500910-d1` |
| Enable APIs | ✅ Done | Google Drive API, Google Docs API, Google Sheets API — all enabled |
| Create service account | ✅ Done | Name: `m4-document-assembly` · Email: `m4-document-assembly@second-modem-500910-d1.iam.gserviceaccount.com` |
| Download JSON key | ✅ Done | Key saved at `C:\Users\User\m4-service-account.json` (outside repo) |
| doctor.py passes | ✅ Done | All 5 checks pass with service account key |

---

## Issue #3 — Provision Shared Drive and folder structure

**Status: ✅ CLOSED (2026-10-30)**

All Drive folders created, all IDs committed to `config/workspace.yaml`. Ledger spreadsheet has `jobs` and `events` tabs. Service account granted Editor role on M4 Document Assembly folder. `workspace.yaml` `approved_revision_id` updated to `13` (commit `bfc36f6`).

| Field | ID |
|---|---|
| `shared_drive_id` | `1TOI0xeXN__be3Mb7jB2QCsPWur_9nQWG` |
| `folders.masters` | `1IH_e6zz_n4RiSQw3YspIYRvjrogbc0jX` |
| `folders.review` | `1cjMRpgw3q0qrAmuMCn9CbAqeSwIkVodd` |
| `folders.approved` | `1uH2N9g0Q2kzfwYFN6hJhPtQgUm0438v7` |
| `folders.quarantine` | `1avRkalemhYLBU7tF1WtARSdNtPzyhnVP` |
| `ledger.spreadsheet_id` | `1CjSkWyKtvWM-OW_9X1vubbC857P_SDvLUFheeP2XcwA` |

---

## Issue #17 — Second teammate onboarding test

**Status: ⏳ READY TO START** — Web UI is fully working. A non-technical teammate can now use the browser app instead of CLI.

| Step | Status | Detail |
|---|---|---|
| Teammate opens browser, navigates to `http://localhost:8000` | ⏳ Not started | Or deployed Cloud Run URL once #33 is done |
| Teammate signs in with Google | ⏳ Not started | Uses Google OAuth |
| Teammate submits a contract via the form | ⏳ Not started | /jobs/new |
| Reviewer approves via browser review UI | ⏳ Not started | /jobs/{id}/review |
| Log all friction points as comments on Issue #17 | ⏳ Not started | |

**Note:** For local testing, the server must be running with the env vars listed in the "Local dev" section below.

---

## Issue #19 — Pilot measurement: manual vs automated time

**Waiting on:** Issue #17 complete.

| Step | Status | Detail |
|---|---|---|
| Record manual baseline time per contract | ⏳ Not started | |
| Assemble ≥5 real contracts using the tool | ⏳ Not started | |
| Log hands-on time per job | ⏳ Not started | |
| Post comparison table as comment on Issue #19 | ⏳ Not started | |
| R-02 posts go/no-go decision | ⏳ Not started | |

---

## Issue #33 — Set up Google Cloud infrastructure (web UI)

**Status: ⏳ READY TO START** — Unblocked as of 2026-10-30. Service account key is ready.

| Step | Status | Detail |
|---|---|---|
| Create Cloud Run service | ⏳ Not started | Record service name in config/cloud.yaml |
| Store secrets in Secret Manager | ⏳ Not started | `GOOGLE_CREDENTIALS_JSON`, `SESSION_SECRET_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `ANTHROPIC_API_KEY` |
| Configure Google OAuth consent screen | ⏳ Not started | Internal users only (Mantix4 org) |
| Fill config/cloud.yaml with resource names | ⏳ Not started | Project ID, service name, secret names, Artifact Registry repo |

---

## Issue #43 — Web UI pilot: ≥5 contracts via browser

**Waiting on:** Issue #33 (Cloud Run deploy).

| Step | Status | Detail |
|---|---|---|
| Non-developer teammates submit ≥5 real contracts via browser | ⏳ Not started | Using deployed Cloud Run URL |
| R-06 Reviewer approves all 5 via browser review UI | ⏳ Not started | |
| Confirm no teammate held a service-account key file | ⏳ Not started | |
| Record hands-on time per contract | ⏳ Not started | |
| Log friction points as new GitHub issues | ⏳ Not started | |

---

## Local dev setup (for running the app on localhost)

**Credentials file:** `C:\Users\User\m4-service-account.json` (service account key — use this)
**Service account email:** `m4-document-assembly@second-modem-500910-d1.iam.gserviceaccount.com`

**Start sequence (cmd):**
```
cd "C:\Users\User\Desktop\M4 Sales Automation\M4-Sales-Automation"
.venv\Scripts\activate
set OAUTHLIB_RELAX_TOKEN_SCOPE=1
set SESSION_SECRET_KEY=dev-secret-key
set GOOGLE_OAUTH_CLIENT_ID=<see Google Cloud Console — OAuth client m4-web>
set GOOGLE_OAUTH_CLIENT_SECRET=<see Google Cloud Console — OAuth client m4-web>
set ANTHROPIC_API_KEY=<your key>
set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\User\m4-service-account.json
uvicorn "web.app:create_app" --factory --reload
```

**App pages:**
- `http://localhost:8000/` — Home / landing page
- `http://localhost:8000/jobs` — Dashboard
- `http://localhost:8000/jobs/new` — Submit a contract
- `http://localhost:8000/jobs/{id}` — Job detail
- `http://localhost:8000/jobs/{id}/review` — Approve / Reject

---

## Next action (resume here next session)

**Primary path — Issue #33 (Cloud Run infrastructure):**
1. Create Cloud Run service in GCP console → record service name in `config/cloud.yaml`
2. Create Secret Manager secrets: `GOOGLE_CREDENTIALS_JSON`, `SESSION_SECRET_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `ANTHROPIC_API_KEY`
3. Configure Google OAuth consent screen (internal users only)
4. Fill in `config/cloud.yaml` with project ID, service name, secret names, Artifact Registry repo

**After #33 is done:**
- Issue #35 (Dockerfile + Cloud Build) — automated, Claude Code implements
- Issue #43 (Web UI pilot) — ≥5 contracts via browser on Cloud Run

**Alternative (no infra needed):** Issue #17 — teammate onboarding test on localhost.

**Everything on `main` is clean and pushed to GitHub.**
