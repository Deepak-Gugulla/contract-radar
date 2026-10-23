# Validation — October 22, 2026

## Verified locally

- Python 3.12; Streamlit 1.66.1; scikit-learn 1.9.1.
- **22 automated tests passed**, including real Streamlit AppTest execution.
- Core tests: contract classification; C2C-negative precedence; explicit W2-only exclusion; related titles; hourly rates; US region filtering; exact hour boundary; unknown/future/date-only timestamps; newest-first ordering; exact URL and requisition deduplication; distinct vacancy preservation; SQLite restart persistence; independent status and catalog updates; refusal to use a public data repository; GitHub conflict retry; Ashby last-publication provenance; unlisted Ashby exclusion; Greenhouse update-time rejection.
- UI tests: login gate; Save; Viewed; Applied; Skip; saved-list navigation; application rerun/restart with persisted history.
- Streamlit app rendered through AppTest with a real collected contract and no exceptions. Browser/mobile visual inspection was not performed; responsive layout uses Streamlit columns and a mobile CSS breakpoint.

## Real public source run

All six configured boards returned successfully in the validation collection:

| Board | API | Listings returned | Related titles |
|---|---|---:|---:|
| Concurrency | Lever | 4 | 2 |
| itD Tech | Greenhouse | 19 | 1 |
| Outpost | Ashby | 14 | 0 |
| GreenLight Workforce Solutions | Ashby | 27 | 0 |
| Comfy | Ashby | 6 | 0 |
| Databricks | Greenhouse | 903 | 22 |
| Total | | 973 | 25 |

One listing passed the default contract/region/C2C exclusions:

**Senior Data Engineer (Contract) — Concurrency**

- Location: Brookfield, WI; remote.
- C2C: unspecified, needs recruiter confirmation.
- Hourly rate: not found in the source text.
- Original posting date: unknown (Lever does not establish it here).
- Original listing: https://jobs.lever.co/concurrency/182c9a96-10c4-49a0-aec1-aeb9315bde51

This result is real source data, not a demo fixture. It does **not** qualify as a verified posting from the last 24 hours. `real-results.json` contains its metadata; `live-collection-report.json` contains collection health. The sample source set is deliberately small and is not an exhaustive contract-job search.

## Pending authenticated acceptance tests

- Creation of the public code and private data GitHub repositories.
- Live Contents API writes with the user's restricted data-repository token.
- Streamlit Community Cloud deployment and private audience selection.
- Save → cloud reboot → verify Saved history.
- A successful scheduled GitHub Actions run and its persisted results.

No deployed website or remote repository URL has been claimed. Account authorization and available publishing capabilities are required to complete these steps.
