# First live pass — 2026-10-21

Status: phases 0–1 complete; stopped at Gate 1 for Kyle's review. No paid provider call has been made.

## Setup and baseline

- Started from `master` at `9568d1c`; working branch `live/first-pass`.
- Kyle approved leaving the four existing untracked planning/patch files untouched.
- Actual environment: Linux/bash, Python 3.12.3 in the existing `.venv`, Node 24.11.0, npm 11.6.1.
- Installed `api/requirements.txt`, pytest and respx (already satisfied); `npm install` and `npm run build` passed.
  Restored npm's five incidental lockfile metadata additions; no dependency change is included.
- Preserved the existing ignored `.env`, credentials, `.cache/` and `data/raw/`.
  Set live mode, model caps $3/run and $20/day, Tavily caps 60/item and 2,000/day, concurrency 2, thinking off.
  All inspected quality settings match their code defaults. Key presence reports true for both providers and admin;
  Kyle confirmed the provider keys are ready. No credential value was printed.
- The initial sandboxed pytest attempt stalled in Starlette TestClient/AnyIO thread dispatch. The same first test
  passed outside the restricted sandbox in 0.70 s; provider HTTP is intercepted by the test fixture.
- The first completed suite found one test assuming 999 credits exceeds any configured daily cap. With this pass's
  2,000-credit cap, the assertion was invalid. Changed only that test to use configured caps plus one.
  No production budget checks, prompts, quote gates or answer-key data were changed.
- After that correction: **153 passed, 2 skipped in 10.91 s**.

Mock baseline run: `20261021-065904-1e2dc4`, saved outside `runs/` at
`/tmp/speccheck-first-pass-mock-baseline.json`. The post-test-fix eval
`20261021-070234-ee2555` has the same panel and gate counts, saved at
`/tmp/speccheck-first-pass-mock-after-test-fix.json`.

| Panel | Mock baseline | Live |
| --- | --- | --- |
| Right calls | 8/8 | Not run |
| Planted problems caught | 6/6 | Not run |
| Clean packages wrongly flagged | 0/2 | Not run |
| Passing fixes | 2/5 | Not run |
| Claims retained | 48/48 (0% dropped) | Not run |
| Web values retained | 19/20 (5% dropped) | Not run |

Mock cost and latency are fixture measurements, not evidence of paid provider performance.

## Gate 1: documents

`fetch_docs.py` kept all 13 already-downloaded target files; no URL was fetched and there were no FAIL lines.
`check_pdfs.py` completed. A separate manifest-target check opened every required PDF with PyMuPDF:
none is encrypted and none has a page with fewer than 200 native text characters.

| Path under `data/raw/` | Pages | Native text characters |
| --- | ---: | ---: |
| `specs/cps_07_84_00.pdf` | 5 | 12,412 |
| `specs/cps_26_51_00.pdf` | 23 | 61,750 |
| `c01/sti_specseal_lci_tds_2025.pdf` | 3 | 9,407 |
| `c02/3m_c-aj-2738.pdf` | 1 | 3,839 |
| `c03/3m_ic15wb_2005.pdf` | 4 | 7,563 |
| `c04/hilti_w-l-2078.pdf` | 2 | 2,738 |
| `c05/lithonia_blt_2x4_2024-07.pdf` | 11 | 41,218 |
| `c06/lithonia_ldn6_2017-10.pdf` | 4 | 12,693 |
| `c07/lithonia_2tl4_2022-11.pdf` | 3 | 8,984 |
| `c08/lithonia_lqm_2019-09.pdf` | 2 | 4,436 |
| `samples/s1/3m_ic15wb_rev_b.pdf` | 2 | 10,700 |
| `samples/s3/lithonia_2blt4_adp_2019-07.pdf` | 7 | 29,926 |
| `samples/s4/hilti_fs-one_max_tds.pdf` | 1 | 2,328 |

The broad PDF checker also saw pre-existing uploads: three synthetic OCR PDFs without text, two synthetic
smoke PDFs with 127 text characters each, and their `case.json` metadata (reported as NOT A PDF).
These are outside the required manifest and do not indicate missing or scanned target documents.
Table detection has low fill rates on the old 3M sheet (9/389 cells, 2%) and the firestopping spec
(22/201 cells, 11%); native text is readable, but table detection is not evidence of accurate model extraction.

## Spend ledger

| Checkpoint | Token Factory USD | Tavily credits |
| --- | ---: | ---: |
| Before setup | 0 | 0 |
| After mock baseline and document checks | 0 | 0 |
| After test correction and mock re-eval | 0 | 0 |

At the last checkpoint `.cache/budget/2026-10-21.json` does not exist;
`budget.today()` returns `{"usd": 0.0, "credits": 0.0}`. This is the local ledger, not console billing verification.
Pass ceilings remain $20 and 2,000 credits across the entire pass.

## Reproduce phases 0–1

```bash
.venv/bin/python -m pip install -r api/requirements.txt pytest respx
(cd web && npm install && npm run build)
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/speccheck-first-pass-mock-baseline.json
.venv/bin/python scripts/fetch_docs.py
.venv/bin/python scripts/check_pdfs.py
```

Use an unrestricted local shell for pytest in this environment. Tesseract is not installed here.
Phase 2 starts only after Kyle reviews Gate 1. Deployment, cloud resources and paid providers remain untouched.
