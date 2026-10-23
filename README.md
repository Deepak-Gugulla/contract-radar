# Contract Radar

A personal Streamlit dashboard for US Data Engineering contracts, built for **$0/month**. No paid AI service, domain, database, or API key is required. Deployment requires your own free GitHub and Streamlit Community Cloud accounts.

**Delivery status:** implemented and tested locally with real public ATS data. Not yet published to a GitHub account or deployed to Streamlit; account connection and publishing authorization are pending. See `VALIDATION.md` for verified behavior and limits.

## What it does

- Collects documented public Greenhouse, Lever, and Ashby job-board APIs, plus explicitly authorized JSON feeds. ATS boards are company career portals; no arbitrary site scraper is used.
- Finds data engineering, ETL/ELT, Snowflake, Cortex, Fabric, Databricks, Azure/AWS/GCP data engineering, Palantir/Foundry, analytics engineering and related titles.
- Requires contract evidence. Hides explicit W2-only/no-C2C roles. Includes C2C-unspecified contracts with a clear label. C2C mention is not verified recruiter acceptance.
- Defaults to Central/Eastern states and explicitly US remote roles. Includes whole states that span time zones (e.g. TX/KS/NE/SD/ND/FL/IN/KY/TN); this is a regional approximation, not city-level time-zone geocoding. Remote jobs without confirmed US eligibility have a separate opt-in.
- Uses original posting dates in descending order. Unknown originals appear last. Filters: 1, 3, 6, 12 and 24 hours. Unknown, date-only and future times never qualify as verified recent.
- Save, Skip, Applied, Viewed and Reset; separate persistent activity records retain snapshots even if the active catalog ages out. Apply opens the source link; it never applies automatically. Viewed is explicitly marked, not tracked across an external browser tab.
- Free local TF-IDF NLP extracts relevant sentences from descriptions. This is lightweight extractive text analysis, **not a generative LLM**. It never changes chronological order or makes eligibility decisions.
- Manual refresh, source-health diagnostics, JSON import/export, and a two-hour GitHub Actions collector.

## Architecture and $0 strategy

| Component | Choice | Cost control |
|---|---|---|
| Code | Public GitHub repository `contract-radar` | No secrets or personal activity committed |
| Scheduler | Standard Ubuntu GitHub Actions runner in public code repository | Public standard runners are free; workflow refuses private repositories |
| Private persistence | Private GitHub repository `contract-radar-data`, JSON documents | No Actions run in this repository; no paid database |
| UI | Streamlit Community Cloud | Free plan; one private app supported |
| AI/NLP | scikit-learn running inside the UI | No external inference or credits |
| Local development | SQLite | No external account needed |

The data repository is checked for privacy before use. GitHub Contents API updates use SHA-based compare-and-swap and retry against the latest document. Catalog and user activity are separate, so collection does not overwrite activity. No silent ephemeral fallback is allowed with `REQUIRE_DURABLE=true`. This is suitable for one person's low-write workload, not a multi-user database. Data has Git history; deleting a current record does not erase that history.

## 1. Run locally

Use Python 3.12. In the extracted `contract-radar` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python collect.py
streamlit run app.py
```

On Windows activate with `.venv\Scripts\activate`. The local URL is normally `http://localhost:8501`. SQLite is stored at `data/local.sqlite`, ignored by Git. Local mode displays a warning because this file alone is not durable on free cloud hosting.

## 2. Create GitHub repositories

Create two repositories under your GitHub account:

1. **Public** `contract-radar` for this source code. Do not put secrets, personal imports, SQLite files or downloaded activity exports in it.
2. **Private** `contract-radar-data`. Initialize it with a README so `main` exists. Keep this repository private.

Push this project into the code repository (replace YOUR_USERNAME):

```bash
git init -b main
git add .
git commit -m "Build personal contract job radar"
git remote add origin https://github.com/YOUR_USERNAME/contract-radar.git
git push -u origin main
```

The delivered source also includes `requirements-lock.txt` recording the tested dependency versions. `requirements.txt` pins the two direct dependencies.

## 3. Create narrowly scoped persistence credentials

In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens:

- Select only `contract-radar-data`.
- Repository permission: **Contents: Read and write**; metadata read is automatic.
- Set an expiration you will remember to renew.
- Copy the token directly into Streamlit Secrets and GitHub Actions Secrets below. **Do not paste the token into chat or commit it.**

In the **code** repository → Settings → Secrets and variables → Actions, add:

```text
DATA_REPO = YOUR_USERNAME/contract-radar-data
DATA_TOKEN = your fine-grained token
```

No Actions workflow or paid runner is needed in the private data repository. Do not switch the collector to private code unless you independently enforce $0 billing; the provided workflow deliberately skips private repositories. Do not enable paid add-ons or larger runners. Other GitHub usage in your account is outside this project's cost controls.

## 4. Generate your dashboard password hash

Use a long random password from a password manager. This command prompts without displaying it:

```bash
python -c 'import getpass,hashlib; print(hashlib.sha256(getpass.getpass("Dashboard password: ").encode()).hexdigest())'
```

The digest goes into Streamlit Secrets. Keep the actual password in your password manager. This simple single-user password gate is additional protection; **Streamlit's private-app access restriction should be the primary access control**. It is not a full identity system and has no persistent brute-force throttling.

## 5. Deploy to Streamlit Community Cloud

1. Open https://share.streamlit.io/ and sign in; connect your GitHub account using its authorization flow.
2. Create an app → deploy from an existing repository.
3. Repository: `YOUR_USERNAME/contract-radar`; branch: `main`; entrypoint: `app.py`.
4. Select Python **3.12** in advanced settings.
5. Paste the contents of `.streamlit/secrets.toml.example` into the Secrets field, replacing every placeholder. Keep `REQUIRE_DURABLE="true"`.
6. Click Deploy. The app's password gate blocks the dashboard even if the initial hosting visibility is public.
7. In app Settings → Sharing → Who can view this app, select **Only specific people can view this app**. Allow only your own email. Community Cloud supports one private app; if your account already uses that allowance, resolve that before claiming this deployment is private.
8. Open the resulting `https://...streamlit.app` URL and sign in. Click Collect now.
9. In GitHub's code repository → Actions → Collect public job boards → Run workflow. Verify the run succeeds. The default schedule is `17 */2 * * *` (UTC, every two hours at minute 17).
10. Save a real job; reboot the Streamlit app; confirm it remains in Saved. This is the final live persistence acceptance test and needs authenticated accounts.

For local testing of GitHub persistence, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace placeholders. The CLI collector reads environment variables, not Streamlit's TOML. Set `DATA_REPO`, `DATA_TOKEN`, and `REQUIRE_DURABLE=true` in your local process environment to test the CLI backend.

## 6. Add useful sources

Edit `sources.json` and commit it to the **code** repository. The board name comes from the company's real ATS career URL. There is no universal API that discovers all companies or all contracts. The supplied boards are a working seed list, not complete US job coverage.

```json
{"type":"greenhouse","board":"COMPANY_BOARD_TOKEN","company":"Company name"}
{"type":"lever","board":"COMPANY_SITE_NAME","company":"Company name"}
{"type":"ashby","board":"CASE_SENSITIVE_BOARD_NAME","company":"Company name"}
```

For a permitted JSON feed, supply an HTTPS endpoint with an object containing a `jobs` array, whose items follow `import-template.json`:

```json
{"type":"json_feed","board":"unique-feed-name","company":"Feed owner","url":"https://example.org/authorized-feed.json","permission_confirmed":true,"label":"Authorized feed"}
```

Use only sources whose access and reuse are permitted. The sample ATS adapters call their documented public read APIs. They do not bypass authentication, bot blocks or access restrictions. Source errors are visible. Add staffing firms with actual contract inventory to improve C2C coverage; don't expect startup/company ATS boards to contain many C2C roles.

### LinkedIn alerts

Create LinkedIn job alerts in your own account. Copy job details you are authorized to use into `import-template.json`, replacing all placeholders, then upload through the dashboard. Do not use the example as a real job. An authorized third-party feed can use the JSON-feed adapter. This project **does not automatically read email or collect all live LinkedIn jobs**; there is no assumed free LinkedIn jobs API, no credential/cookie scraping, and no private API bypass. Relative alert text such as “2 hours ago” is not an exact original posting timestamp; leave `posted_at` null.

## Date integrity

| Source | Treatment |
|---|---|
| Greenhouse `first_published` | Original timestamp when present and timezone-aware |
| Greenhouse `updated_at` | Never used as the posting date |
| Lever public API | Original date unknown; creation/update fields not assumed to mean publication |
| Ashby `publishedAt` | Last publication; shown separately because it may be a repost |
| Manual/authorized feeds | `posted_at` accepted only as an explicit original ISO timestamp with timezone; importer must verify provenance |
| First discovery / alert receipt | Kept separate; never used to claim freshness |

Therefore a job collected moments ago may be absent from the 1-hour view. This is intentional. Unknown originals are visible under Any time. UI timestamps display America/New_York; collection records are stored in UTC.

## Deduplication and retention

Exact canonical URLs merge across sources after tracking parameters are removed. Same employer + explicit requisition ID also merges. Different URLs without a shared requisition ID remain separate to avoid collapsing distinct vacancies. This is conservative cross-source deduplication, not perfect fuzzy identity resolution.

The catalog retains at most 5,000 related records; activity snapshots persist separately. A source disappearing or failing does not delete saved activity. Previously seen jobs may have closed; the original application page remains authoritative. There is no automatic closed-job verification or guaranteed stale-listing removal in this version.

## Operational limits

- Every two hours is scheduled collection, **not a real-time firehose**. GitHub may delay or drop queued scheduled runs; public schedules can be disabled after 60 days without repository activity. Re-enable in Actions and keep source configuration maintained.
- Manual refresh has a five-minute UI cooldown. Parallel sessions can still initiate overlapping collections; writes merge with conflict retries.
- Free Streamlit apps can sleep. GitHub collection runs independently while the UI is asleep. Wake-up takes time.
- ATS and GitHub rate limits, source outages and token expiry can interrupt collection. Previous data remains available if storage is reachable; collection health exposes failures.
- Region and employment extraction are conservative text rules, not legal/work-authorization checks. Ambiguous locations or contract descriptions can be missed. Review the original posting.
- No promised C2C confirmation, exhaustive LinkedIn coverage, exact original timestamps when absent, uninterrupted hosting, or unlimited throughput.
- Durable GitHub API behavior is unit-tested with simulated conflicts; live authenticated write/reboot testing must be completed during deployment.

## Files

`app.py` UI and login; `collect.py` CLI; `radar/collectors.py` adapters; `radar/core.py` normalization/filtering/dedup; `radar/store.py` SQLite/GitHub storage; `radar/assistant.py` local NLP; `sources.json`; `.github/workflows/collect.yml`; `.streamlit/` theme and secret example; `tests/`; `VALIDATION.md`; `live-collection-report.json`; `real-results.json`.

## Official references checked during implementation

- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.greenhouse.io/job-board
- https://github.com/lever/postings-api
- https://developers.ashbyhq.com/docs/public-job-posting-api
