# Customer-feedback release evidence — October 28, 2026

**Shipped and frozen:** https://speccheck-wongywrongys-projects.vercel.app . PRs #16 (infrastructure), #15 (product), #17 (recording/fallback) and #18 (image-build fix) are merged. Runtime source is `14ddb6d`, pinned image `d5b22ed5…`; the new endpoint uses the original persistent filesystem. The frozen runtime passed every public gate below.

## Verification

- Python: 771 passed, 2 skipped. Tests prohibit provider calls.
- Mock browser journeys: 17 passed, including the matrix, manual-review persistence and memo.
- Presentation checks and production web build passed.
- Four additional fallback-admission tests passed: missing report runs, same-day live report skips, a mock report does not count, and provider calls stop at the December 15 cutoff.
- The frozen image passed a credential-free, network-disabled check of all 13 locked PDFs, ten recorded results, the new score panel, package API, native PDF PNG and memo route. See `packaging.json`.
- Raw mock panel remains 6/8 calls, 5/6 problems, 0/2 false alarms, 0/5 passing fixes.
- First sandbox attempts could not run TestClient/Chromium; the successful runs used local networking outside the sandbox. Those failures did not spend provider credits.

## One final live recording

`runs/recorded/20261028-065522-3dd974/`: eight cases plus s3 and s4, which together cover every tray and watched item. All ten results are valid with no warnings. Existing provider caches were reused. No second full live run was made.

| Measure | October 22 | October 28 |
| --- | --- | --- |
| Right calls | 6/8 | 4/8 |
| Planted problems caught | 5/6 | 4/6 |
| Major false alarms on clean cases | 0/2 | 0/2 |
| Passing replacements | 0/5 | 0/5 |
| Unnecessary notes | 1 | 2 |

Every changed decision and the remaining disagreements:

- **c01: approve → approve with note.** The current extraction treats ordinary sealant properties as configuration-specific, producing Specify lines; current-document revision remains unconfirmed. This is an unnecessary note, not a measured major false alarm. The submitted product's quoted label is not proof that it is an ordering option.
- **c04: send back → approve with note.** The old extraction quoted PVC/ABS/FRPP/CPVC/PVDF/PEX and failed the steel-pipe requirement. The new extraction did not retain comparable pipe-coverage claims, so the code leaves it unconfirmed and misses that planted problem. Unknown is not silently changed to failure.
- **c05 remains approve with note versus expected approve.** Missing L70/warranty evidence, unresolved selected dimming configuration, and a different revision still produce notes.
- **c06 remains approve with note versus expected send back.** The web reading finds a newer revision without a quote-backed changed value, so the revision difference is a note and the planted currency problem remains missed.
- **c02, c03, c07 and c08 retain their previous decisions.** c08 took 350 seconds; this known set is not a latency benchmark.

The strict case evidence gate **fails**: wrong calls, missed problems, unnecessary notes and no evidenced passing replacement. The answer key and reviewed checklists were not changed. No claim of improved accuracy, a passing replacement or a planted-problem Investigator rescue is justified.

## Wrong-spec check

Live run `20261028-070445-386da4`: **0/14 approved**, **14/14 not applicable**, no errors. It covers every case under the other section, the off-topic PDF, the three Try-one sheets under the wrong section, and Schlage under both CPS sections. Results are a separate block in the recorded scores; cached usage is retained. No fresh model or web charge was needed.

## Accounting

Shared local ledger before this continuation: **$1.24585706 / 84 credits today**. Recording: **$0.59806296 / 46 credits**. Wrong-spec check: **$0 / 0 credits**. Local total after these checks: **$1.84392002 / 130 credits today**, with no open holds. These model USD amounts and Tavily credits are separate units.

The public deployment has a separate judging ledger. Hosted smoke/browser charges and the scheduled fallback's isolated $0.50/40-credit allowance must be reported separately. Ledger snapshots are retained beside this report. Existing W1/W3 evidence and screenshots remain in the parent directory.

## Daily fallback commissioned

[GitHub Actions run 40649387428](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/40649387428) succeeded. Its real report is visible at `/api/watch` on the stable public URL: **October 28, 07:22:37 UTC · GitHub Actions · 1 item, 1 flagged**. c07 is discontinued, with its quoted manufacturer notice. Actual isolated ledger: **$0.06667272 / 13 credits**, no holds. `github-recheck-ledger.json` is the charge record; the report’s $0.073797 is usage-equivalent and includes cached requirement cost. No Nebius Serverless Job is claimed. The daily 09:00 UTC schedule is configured; the first cron event has not yet been observed.

The recorded live memo was rendered and printed from the exact release image, with no credentials or paid calls: `local-recorded-memo.pdf` (15 letter-size pages), screenshot and `memo-browser.json`.

## Earlier Package D work recovered

The prior Claude session already ran all three Try-one products and the UBC/Schlage pair live in `20261028-040006-28d2af`. The source results remain on disk; `prior-package-d.json` preserves their hashes, real traces and measured charges. Two of four items triggered primary investigations (Metacaulk and TREMstop); **0 resolved, 0 capped**. The Schlage draft in that earlier test did not match after a mechanical first-30 trim. This release does not repeat that experiment or claim an Investigator rescue. The production bring-your-own journey is checked separately below. Kyle’s original manual timing sheet is preserved here; no human timing or permissioned practitioner quote has been supplied.

## Public release verification and freeze

The no-admin [smoke](smoke.txt) passed with a fresh Nemotron call, charged **$0.00064140 / 0 credits**. The new recording, source PDF images, package API, public memo/PDF and Scoreboard were verified through the stable Vercel URL.

Fresh browser contexts, actual API traffic, no fabricated replies:

| Journey | Result | Fresh charge | Evidence |
| --- | --- | --- | --- |
| Off-topic upload → Not checked | Pass | $0 / 0 cr | `public/a-trace.json` |
| Try-one upload → quoted Review → Outcome | Pass | $0 / 0 cr on successful run | `public/b-trace.json` |
| UBC spec → draft 65 rules → edit/delete to 30 → Schlage → scoped Review → Outcome | Pass | $0 / 0 cr (cached) | `public/c-trace.json` |
| Seven-item tray → streamed completion → matrix → Review → Outcome | Pass | $0.02240220 / 4 cr | `public/d-trace.json` |
| Same PDF under firestop and lighting → only matching section proceeds | Pass | $0.00041460 / 0 cr | `public/e-trace.json` |
| Check approved now → fresh c07 check → discontinued alert | Pass | $0.00482730 / 7 cr | `public/check-approved.json` |
| Real recorded package memo printed; updated Scoreboard | Pass | No scan | `public/memo.pdf`, `public/memo-scoreboard.json` |

The first Try-one attempt finished a valid scan but its capture called `img.decode()` while the PDF view was loading. All three native PNGs were fetched and decoded successfully afterward. The capture helper now waits for the current images to finish loading; the successful cached retry charged $0. The original attempt and its **$0.00470940 / 0 cr** charge remain in `public/b-attempt1-trace.json`. No runtime code or provider cache was changed to obtain that retry.

Local validation was 771 Python passes / 2 skips plus 4 passing fallback-admission tests. GitHub CI on the final code reported **771 passes / 6 skips**, with 17 browser passes, presentation and production build passing. CI and local environments skip different document/OCR-dependent checks; the release image separately verified all 13 locked PDFs offline. The [corrected image pipeline](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/40651206922) is green: it seeds the already verified PDFs from the frozen image by immutable digest instead of retrying the c02 download rejected by the manufacturer on GitHub runners. The hash lock still gates the build.

**Persistent state:** before and immediately after replacement, the judging ledger was exactly **$1.12675158 / 313 credits**. The GitHub report also survived. Final judging allowance remaining: **$73.84025352 / 5,676 credits**, no holds. `public-before-switch.json`, `replacement-health.json` and `public-final-health.json` preserve the observations. The superseded stopped endpoint was deleted with Kyle's explicit approval; its old tunnel address is gone. The persistent filesystem was retained.

**Measured incremental cost for this continuation:** **$0.69773058 model USD / 70 Tavily credits**, broken down in `accounting.json`. Cloud endpoint and CI billing were not measured; the app continues on the approved single 2-vCPU/8-GB endpoint. The daily fallback has its separate $0.50 / 40-credit ceiling through December 15.

**Freeze:** runtime source `14ddb6dda5d1c95c3508af04bc573ba8c45b89c7`, image `ghcr.io/wongywrongy/speccheck@sha256:d5b22ed554d26dac83808ea53155d8a28d03bd3f2c6623171cb6b5321093bb07`, frozen **2026-10-28 07:57:48 UTC**, before Wednesday 19:00 PT. Later commits contain evidence, routing and capture/CI tooling, not changes to the frozen app. See `freeze.json` and `docs/deployment/final-deployment.json`.

**Remaining owner work:** supply manual timings and a permissioned quote if desired, refresh/publish the video from `video/DELTA.md`, fill Devpost and submit. The video branch was left untouched. No improved accuracy, passing alternate, Nebius job execution or unobserved cron run is claimed.
