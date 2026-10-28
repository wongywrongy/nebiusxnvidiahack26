# Customer-feedback release evidence — October 28, 2026

Release candidate based on `e8af541`. The product changes are in PR #15; the infrastructure prerequisite is PR #16. Deployment and the daily fallback must be verified separately before being called shipped.

## Verification

- Python: 771 passed, 2 skipped. Tests prohibit provider calls.
- Mock browser journeys: 17 passed, including the matrix, manual-review persistence and memo.
- Presentation checks and production web build passed.
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
