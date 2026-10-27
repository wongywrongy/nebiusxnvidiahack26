# Release preflight — 2026-10-23

This checkpoint implements a separate read-only promotion check. It does not approve a release, change a
recording or run any providers. The existing case evidence check is a prerequisite, not full release proof.
The Scoreboard now states that distinction. Diagnostic `record_live.py` still preserves complete valid live
runs with honest wrong calls; the original recording and answer keys remain unchanged.

## Evidence required

`scripts/check_release.py` requires all of the following together:

- Complete cases and samples, six new source-labelled blind packages, and the full cases/public-tray/watched
  recording. Stored panels are recomputed from results, attempts and original labels. The public recording's
  stored scoreboard stays cases-only; its extra public items are also checked for promotion.
- Identical current code, model/quality/budget configuration, reviewed requirements, original inputs and
  document-lock hashes. Required native PDFs must still exist, open and match the lock.
- Valid live results, compatible configuration hashes, no replay/cap/provider warnings, complete attempts,
  ordered per-item stage traces and final decisions consistent with code and the trace.
- Saved extraction claims rechecked against their actual submitted PDF pages, including identity, value,
  unit, applicability and selected-configuration evidence. Base models may extend to a grounded selection;
  a shared driver code cannot bind one product to another product's selection.
- Explicit verification inputs, outputs and hashed source archives for every item. Promotion replays the
  existing web quote gate and coded comparison, so omitted web checks and unrelated availability quotes fail.
- A passing replacement with every applicable reviewed/project requirement, current-document and availability
  checks, each with a quote in its hashed archive. Merely omitting a check cannot make a replacement pass.
- A genuine primary Investigator rescue: saved scripted baseline, successful extraction/finish trace and
  attributable recovered comparison/status proof. An outcome enum or revision retrieval alone is insufficient.
- A dated Kyle approval binding the exact hashes of all final artifacts. Each accepted disagreement must
  identify the exact suite/item/miss categories and contain a reason plus quotes on cited frozen PDF pages.
  Raw wrong-call/problem/note counts remain unchanged. Approval cannot waive incomplete or invalid evidence,
  missing passing replacements or missing Investigator recovery.

Web citations must point to the correct archived bytes and contain their quote, with original retrieval
within 24 hours before run start and no later than evaluation completion. This checks source age at the
evaluation; it does not claim the world stayed unchanged afterward. Use an evidence archive for final runs.

## Bundle and file layout

The bundle is a JSON object with six paths, relative to the bundle file:

```json
{
  "cases": "path/to/cases-run",
  "samples": "path/to/samples-run",
  "blind": "path/to/blind-run",
  "recording": "path/to/recorded-run",
  "blind_set": "path/to/frozen-blind-set",
  "review": "path/to/owner-release-review.json"
}
```

Each run needs `manifest.json`, `events.jsonl`, `attempts.json`, `results/*.json` and `scores.json`.
Evaluations now retain their scoreboard inside the run as well as the requested output. New run manifests
record `run_id`, `requested_ids` and an aware UTC `started_at`; a blind run must additionally bind the frozen
set's `validation_set_sha256`. Older artifacts without those fields cannot establish this new release proof.

The blind folder has `inputs.json` with an unlabelled `cases` array, `labels.json` with a separate `labels`
array, and `manifest.json`. Inputs cannot contain answer labels, verified summaries, fixture names or hints.
Each package has a new ID, reviewed section and submitted PDF records (`file` relative to `data/raw/`, source
`url`, `sha256`, `role`). The six primary PDFs must be distinct and outside the locked demonstration set.
Each label includes `id`, `expected.decision`, `expected.problems`, assembly/selection `scope`, and `sources`.
A source contains `file`, `url`, `sha256` and `quotes` (`page`, `text`); each quote is checked on that PDF page.
The manifest records `version: 1`, `prepared_by`, `frozen_at`, `inputs_sha256`, `labels_sha256`, `reviewed_by`
and `reviewed_at`. Review must follow freeze and precede evaluation. Preparation history and independence
still need real evidence; writing a preparer name into JSON does not establish them.

The final owner review records `approved_by`, aware `approved_at`, `artifact_hashes` for cases/samples/blind/
recording/blind_set, and `accepted_misses`. A miss entry has `suite`, `id`, exact `misses` from `wrong_call`,
`missed_problems`, `false_alarm`, `unnecessary_note`, a reason and page-grounded PDF sources under `evidence`.
The preflight report supplies the artifact hashes; the agent must not fill approval fields without Kyle's
explicit acceptance. No actual owner review or blind approval was created in this checkpoint.

## Reproduce

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/release-mock.json
# Expected eval exit 1: unchanged raw 6/8 selection-policy disagreements.
cd web && npm run test:presentation && npm run build
```

Run the read-only check with the same measured model/quality/budget environment as the supplied evidence:

```bash
SPECCHECK_MODE=mock .venv/bin/python scripts/check_release.py path/to/bundle.json --out /tmp/release-check.json
```

Using mock mode for this checking command spends nothing and does not relabel the supplied results: every
result must itself be valid live evidence. Exit 1 and explicit issues mean promotion failed. No auto-approval,
upload, deployment, public-file mutation or provider retry occurs.

## Remaining work

The full mock suite passed **505 tests, 2 skipped in 27.10 seconds** outside the sandbox. Sandboxed attempts
stalled in the local TestClient thread/socket handoff and were interrupted; they are not counted as passes.
Presentation checks and the web build passed. The raw mock panel remains **6/8 calls, 5/6 problems, 0/2 major
false alarms, 0/5 passing fixes**, 48/65 claims and 8/20 web values retained, with $0 / 0 fresh spend.
`bundle.pending.json` deliberately points to the latest mock diagnostic, historical recording and missing
final artifacts. Its actual [promotion report](promotion.json) fails. No approval fields were filled in.

The blind preparation/evaluation command, actual six frozen packages, Kyle's label review and gated full
case/sample/blind runs remain pending. The public release recording, owner dispositions and concrete
deployment preparation/proof are also pending. G2 still lacks a complete passing replacement. See
[ownership](../ownership.md). Local tests are not a new live accuracy panel or hosted durability evidence.
