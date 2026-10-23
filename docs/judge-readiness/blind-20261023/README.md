# Six new-source validation packages — 2026-10-23

**Prepared and frozen, awaiting Kyle's label review. No pipeline evaluation or paid provider call.**
The implementation agent prepared these labels directly from new manufacturer PDFs before running the
application on them. This is a held-out source set, not an independent human study. No claim of blind
accuracy is possible yet. The source selection, unsuccessful download and retrieval times are in
[download-log.json](download-log.json). Six distinct primary hashes are outside the 13-document demo lock.
All six PDFs downloaded with HTTP 200 and have native text on every page; no OCR was needed.

[inputs.json](inputs.json) contains only the submitted packages. [labels.json](labels.json) contains the
separate draft expectations, requirement-by-requirement reasons and exact page quotes. The PDFs remain
under ignored `data/raw/blind/20261023/`. Neither fixtures nor source excerpts are substituted for them.
The [source preflight](source-preflight.json) checked each hash, PDF, page quote and known-set exclusion.
`manifest.json` deliberately has null owner-review fields. The actual check-only invocation refuses this
unreviewed set before creating a run; that refusal is correct, not an evaluated miss.

## Kyle's review table

Approve or edit each draft using the complete PDF and the detailed property rows in `labels.json`.
These are proposals; none is approved by the agent.

| Package | Scope | Draft call / problem | Decisive source evidence | What remains unconfirmed |
| --- | --- | --- | --- | --- |
| b01 — STI SpecSeal SSS | Product data | Approve / none | Page 2: `VOC Content**` / `29.2 g/L`; `Mold & Fungus Growth Rating (ASTM G21)` / `0`. Page 1 prints ASTM E814 (UL1479). | Specific assembly F/T proof remains pending; “up to 4 hours” does not select one. |
| b02 — Tremco TREMstop Acrylic **SP** | Product data, sprayable product | Approve with note / none | Page 2: `VOC Content` / `40 g/L`; `Antifungal` / `Contains an antifungal additive`. Page 1 prints UL 1479 (ASTM E814). | An antifungal additive does not establish a zero ASTM G21 rating. Assembly proof is pending. |
| b03 — STI C-AJ-0113 | Listing only | Send back / spec | Page 1: `F Ratings - 2, 3 and 4 Hr (See Items 1 and 3)` / `T Rating - 0 Hr`. | No field installation is selected. Every listed positive F rating differs from zero T; no selection among those F ratings repairs that mismatch. |
| b04 — STI F-A-1118 | Listing only | Approve / none | Page 1: `F Rating - 2 Hr` / `T Rating - 2 Hr`. | Passing listed equality does not approve an actual device, penetrant, installation or missing product data. |
| b05 — RAB RPLED | Family product data | Approve with note / none | Page 1 prints five-year warranty and DLC premium. Page 2 says `100,000-Hour LED lifespan` and specifies a 0–10 V interface. | No explicit L70 endpoint, numeric MacAdam result or luminaire minimum dim percent. Sensor standby values and a control voltage are different metrics. No SKU is selected. |
| b06 — RAB RTLED | Family product data | Send back / spec | Page 2: `Requires separate 0-10V DC dimming circuit. Dims down to 10%`. | The main driver limit exceeds the reviewed 5% maximum. Missing L70/MacAdam evidence stays unconfirmed; sensor commissioning options do not replace the main driver limitation. |

These drafts do not plant a currency/status problem or infer one from an old date. The application will
still perform its normal web verification. If later sources establish a new contradiction, retain the raw
panel and stop for Kyle's source-grounded adjudication. Do not fit these labels to application output.
Assembly packages review the listed rating relationship only; neither draft asserts field suitability.

After Kyle's explicit decisions, apply only those decisions, update the label hash and freeze time if the
labels change, and save Kyle's name and actual review time in `manifest.json`. Never fill those fields
without his approval. The run digest binds all three files, including that review. G2/G3 authorization is
still required before a live evaluation; review alone does not authorize a cloud deployment.

## Runner behavior and reproduction

The normal eval CLI now accepts `--blind-set`. It validates all six frozen PDFs, page quotes, distinct
new hashes and owner review before starting. It gives the pipeline the input catalog with expectations
removed; scoring receives labels afterward. It saves the exact reviewed set digest in the run manifest
before execution. It cannot replay demo fixtures for a blind run, cannot mix suites, and does not replace
the public eight-case scoreboard. Full release promotion remains `scripts/check_release.py`.

```bash
# No provider calls. Expected exit 2 while owner review is pending:
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --blind-set docs/judge-readiness/blind-20261023 --check

# After explicit label review AND the evaluation gate, using the approved quality profile:
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --blind-set docs/judge-readiness/blind-20261023 --out /tmp/blind-scores.json
.venv/bin/python scripts/campaign_budget.py status
```

For a fresh checkout, retrieve the exact public PDFs without touching credentials or the campaign wallet:

```bash
.venv/bin/python - <<'PY'
import hashlib, json
from pathlib import Path
import httpx
folder = Path('docs/judge-readiness/blind-20261023')
for case in json.loads((folder / 'inputs.json').read_text())['cases']:
    for doc in case['submittal']:
        path = Path('data/raw') / doc['file']
        data = path.read_bytes() if path.exists() else httpx.get(doc['url'], follow_redirects=True, timeout=30).raise_for_status().content
        assert data.startswith(b'%PDF') and hashlib.sha256(data).hexdigest() == doc['sha256'], 'Source changed or unavailable; stop for review'
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(case['id'], 'hash verified')
PY
```

Hash disagreement must not overwrite the frozen source or silently update labels. Preserve the original
download and ask Kyle about the changed URL/quote before preparing a new version.
