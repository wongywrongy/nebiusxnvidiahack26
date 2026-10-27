# Playground validation — October 27, 2026

Local browser evidence uses actual live API replies in fresh private Chromium contexts. No routes were intercepted.
PR #13 is not ready to merge: the tray check hit provider timeouts; the two-spec check is still pending.

| Check | Run | Result | Model USD | Tavily credits |
| --- | --- | --- | ---: | ---: |
| [Off-topic PDF](local/a-trace.json) | `20261027-190514-66b1bf` | Browser flow passed | 0.00095106 | 0 |
| [Try-one RectorSeal](local/b-trace.json) | `20261027-191007-cfd26e` | Browser flow passed | 0.01423110 | 3 |
| [UBC draft + Schlage](local/c-trace.json) | `20261027-193336-2b2fea` | Browser flow passed | 0.09093900 | 8 |
| [Seven-item tray](local/d-trace.json) | `20261027-193730-d9deab` | Failed; retained | 0.06365184 | 0 |

**Accounting:** $0.46614516 settled model spend / 32 credits this push, plus **$0.06365184 held** for two Nano timeouts. The tray row is reserved unknown usage, not a confirmed charge. Total allowance consumed including holds is $0.529797 / 32 credits, within the $2 / 150 local ceiling. Baseline and failed attempts are retained; do not sum only the successful rows.

The historical one-credit Tavily hold was settled at its reserved amount by owner decision on October 27. These two model holds are new and remain unresolved. Paid admission is blocked.

Final local quality profile: `MAX_OUTPUT_TOKENS=65536`, `FIX_MAX_CANDIDATES=1`, concurrency 2; day/run USD cap 2, daily Tavily cap 150. Local validation uses 60 upload admissions/hour for repeated checks; this does not change the production default.

The successful BYO run returned **valid**, with no diagnostics and five matched rules out of 30. Nemotron drafted 33 rows; three were removed to meet the save limit. The unreviewed named-series rule flags `ND Series` against branded allowed identifiers; that literal comparison is a draft-quality limitation, not a claim that the paired Schlage product violates the original UBC specification.

Fixes discovered live: consistent printed claim identity instructions; product documents preferred over broad price books; native tool calls reserve a finishing slot even for parallel requests. Hard quote, option, spend and decision gates remain active. No passing replacement or Investigator rescue is claimed.

Review/Outcome screenshots for a–c were recaptured by reopening their actual stored live results and waiting for all native page images to decode. This was read-only and added no spend. The capture script now waits for decoded pages.

[Off-topic Review](local/a-review.png) · [Try-one Review](local/b-review.png) · [Edited draft](local/c-draft-edited.png) · [BYO Review](local/c-review.png) · [BYO Outcome](local/c-outcome.png) · [Tray failure](local/d-failure.png)

[PDF download verification](pdf-links.json): all five links returned plain HTTPS PDFs under 15 MB with extractable page-one text, including UBC (7 pages) and Schlage (14 pages). Raw PDFs remain outside Git.

Regression: **745 passed / 2 skipped**, production build clean; raw mock panel **6/8, 5/6, 0/2, 0/5**, zero fresh provider charges. No eight-case live evaluation was run.

Cloud preparation: Nebius CLI authenticated, selected eu-north1 project; no endpoint, registry or filesystem has been created. Existing GHCR package is publicly readable; final local-image publishing awaits GitHub package-write authorization. No public deployment or cloud job is claimed.
