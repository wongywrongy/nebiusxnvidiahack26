# Required evidence research — 2026-10-23

G2 remains open. This general retrieval correction does **not** produce a passing replacement or prove
release readiness. Original expectations, reviewed requirements and the historical recording are unchanged.

The preceding targeted trace showed that missing requirements were never presented to the Investigator:
it received only extracted claims. Candidate availability could also skip investigation once revision or
comparable values were found. The fix caller now supplies applicable **property names**, including reference
dependencies, and explicitly requires availability research. No required values or expected decisions are
sent. The Investigator is told that a live product page or absent discontinuation notice cannot establish
availability and that missing configuration stays unconfirmed.

After research, the bounded three-source read prioritizes the returned document, its fetched status quote
and new supplementary pages before older scripted pages. Exact identity/value/scope/selection/status gates
still decide. [Old/new prompt and context](prompt-before-after.json), [runtime patch](source.patch).
Applying that patch to clean `53eb99a` reconstructs the measured runtime hash
`c3c5ed3a0263d3b606584abc6d81410a4866a21596efeb9222907cc54adc463f`;
[actual reconstruction](source-reproduction.json).

| Observed behavior | Before | After |
| --- | --- | --- |
| Missing requirement absent from accepted extracted claims | Not included as a research gap | Applicable property names included |
| Unknown replacement availability with other document proof | Could skip research | Explicit research requirement |
| Newly fetched supporting/status pages | Returned document plus older pages could displace them | New document/status/support prioritized, at most three |
| Actual passing replacement | 0/2 | **0/2** |

## Measured runs and remaining misses

Full mock suite: **621 passed, 2 skipped in 31.67 s**, [output](pytest.txt). Six new tests exercise revision-
present gap triggers, unchanged ordinary verification, active status, source priority and the actual native-
tool request. Existing caller tests also assert required-property/availability forwarding; their separate
post-edit run passes **38 tests in 0.20 s**. The raw mock panel stays **6/8 calls, 5/6 problems, 0/2 major
false alarms, 0/5 fixes**, zero invalid items, one unnecessary note, 48/65 claims and 8/20 web values;
[score](mock-score.json), fresh $0 / 0. Expected exit 1 preserves the disclosed selection-policy disagreements.
No frontend code changed. [Both preceding-source CI workflows](preceding-ci.json) pass, including mock
browser/build/presentation checks; no current-source CI pass is inferred.

Targeted live **`20261023-071700-8a9e33`**:

| Item | Correct call / caught problem | Passing fix | End-to-end time | Fresh model USD | Fresh web credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | Send back / currency | 0/1 | 54.947 s | 0.0238437 | 4 |
| c07 | Send back / discontinued | 0/1 | 81.188 s | 0.0432930 | 8 |

Totals: **2/2 calls, 2/2 problems, 0/2 passing fixes**; no clean item requested. Fresh **$0.0671367 / 12**.
Times include partly cached research, not cold/provider-only latency. Claims **56/209 retained, 73.2% dropped**;
web **54/110 retained, 50.9% dropped**. Zero invalid items, warnings, provider errors, caps or observed 429s.
Zero primary scripted-unconfirmed items and primary investigations. Four **replacement** investigations,
none capped: one `not_found`; three `found` with `revision_only`, `not_resolved` and `values_confirmed`.
These are not four successful fixes or primary rescues. [Score](score.json),
[exact steps and candidate check evidence](diagnosis.json), [events](events.jsonl).

| Candidate source | Accepted proof | Still unconfirmed |
| --- | --- | --- |
| [3M IC 15WB+](https://multimedia.3m.com/mws/media/207329O/3m-fire-barrier-sealant-ic-15wb-technical-data-sheet.pdf), two returned URL variants | VOC in one read; standards; fetched-source comparison | G21, selected assembly F/T relationship, availability; VOC absent from the second read |
| [Starco SLLT](https://starcous.com/wp-content/uploads/2024/10/Spec-Sheet-SLLT-LED-Troffer.pdf) | L70, warranty, DLC | MacAdam, minimum dimming, availability |
| [Williams LT](https://hew.com/specifications/LT_led.pdf) | L70, warranty, MacAdam | Selected DLC/driver configuration, availability |

The new searches still fail to obtain an exact availability statement. A product listing is not substituted.
Missing source evidence and unselected options are not provider failures or proven spec failures. No original
answer-key contradiction or changed-world claim is inferred. The model still sometimes labels a copyright
or SDS date as revision metadata; a matching fetched value does not independently prove the newest sheet.
That source-type/currency interpretation remains an open issue, not a claim that currentness is established.

The archive/quote/trace check passes for **these two items only**, using the exact live profile;
[consistency](consistency.json). It is not the complete release promotion check. An attempted default-profile
invocation correctly refused configuration mismatch; the matching-profile check above is the relevant result.
No broader follow-up full-set run, blind evaluation or final recording was consumed.

Actual campaign **$2.6351023 / 438 credits**, day **$1.1483655 / 80**, zero holds or persistent block;
[campaign](campaign-status.json), [day report](daily-ledger.json). Engineering since the original pass adds
**$1.5764973 / 140**. The earlier owner account-wide **$2.13 / 421** and read-only API **415** observations
precede this run. Their [unresolved reconciliation](../scope-binding-20261023/README.md) remains historical;
no new dashboard match, cached-input discount amount, ledger correction or invoice audit is claimed.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/replacement-research-mock.json
# Expected mock exit 1, raw key unchanged.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/replacement-research-live.json
.venv/bin/python scripts/campaign_budget.py status
```

No provider keys, resource creation, real wallet transfer, registry publication or owner approval are included.
