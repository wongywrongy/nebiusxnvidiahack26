# Who does what — 2026-10-23

The agent owns implementation, execution and evidence. Kyle owns domain judgments, gate acceptance,
private account access and release approval. Approval does not transfer the engineering work to Kyle.
The active readiness goal is **not complete**; the following unfinished implementation remains agent-owned.

## Completed and recorded

| Work | Evidence |
| --- | --- |
| First provider spikes and first-pass cases/samples, original recording and local judge walk | [First-pass audit](../live-first-pass/completion.md); original recording unchanged |
| Reviewed requirements and strict unselected-configuration policy | [Dated policy/gate ledger](../judge-readiness.md); original keys/checklists unchanged |
| General chunk, identity, quote/value, source freshness, replacement citation and Investigator attribution guards | [G2 before/after evidence](g2/live-validation.md) |
| Local campaign reservations, failed/retried usage, unknown-usage holds and UTC-crossing admission | [Current verification](reliability-20261023/verification.json); local disk only |
| Linked-PDF Tavily fallback, independent document cache age/credits, one-hop bound | [c07 retry](reliability-20261023/c07-score.json): correct call, no passing replacement, fresh $0 / 1 credit |
| Invalid watch result cannot claim no change | Regression in `tests/test_recheck.py` |
| Browser upload/review/edit/outcome/re-check/reload/reset and failure tests | Eight real Chromium tests against mock API; no new live-browser proof |
| Required PDF lock/readability preflight and fail-closed Docker build | [13-document report](reliability-20261023/document-preflight.json); all have native text |
| Authenticated, idempotent controller launch, full history, mandatory secret selectors and quality forwarding | Fake CLI tests; nightly workflow uses controller and remains disabled |
| Controller job allowances, one-session claims, sealed child wallets and guarded settlement/publication | [Offline protocol checkpoint](controller-20261023/README.md); no shared job write path or hosted proof |
| Read-only smoke mode; invalid/replayed evidence rejected as fresh deployment proof | `tests/test_smoke.py`; hosted smoke remains pending |

Current Python/controller verification: **435 passed / 2 skipped**. Earlier frontend verification: eight
browser tests, presentation checks and build pass; no frontend change or rerun in the controller checkpoint.
Raw mock remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing replacements**.
Actual cumulative provider spend is **$1.4867368 / 359 credits**, with no outstanding holds at this checkpoint.

## Still mine to finish

1. **G2:** obtain and verify an actual complete replacement evidence bundle. The linked Acuity CPX PDF
   returned no Tavily text; the product page does not establish L70, warranty, MacAdam, dimming or availability.
   c03 still lacks mold/assembly proof. No unknown check may be turned into a pass.
2. **Cloud controller:** finish remote authority handoff and explicit writer-cutover tooling, preserving the
   actual wallet and fencing the original before activating a copy. The allowance/claim/child-wallet/receipt/
   settlement protocol is implemented with isolated local tests; the actual campaign wallet has not moved.
   Prove the private mounted filesystem, single-VM writer, restart and receipt persistence on the approved host.
   VM reboot/replacement and interrupted-import recovery remain fail-closed and need explicit reconciliation.
3. **Release preflight:** require complete cases, samples and reviewed blind-set evidence, compatible immutable
   configuration/code/document identities and explicit release dispositions. Diagnostic recording must remain
   able to preserve honest wrong calls. Targeted success cannot establish release readiness.
4. **Blind preparation:** independently prepare six new source-labelled packages and freeze URLs, PDF hashes,
   page quotes, selection/assembly scope and draft labels before pipeline evaluation. Keep labels outside inputs.
5. **After G2/G3 sign-off:** run the authorized final cases/samples/blind checks, diagnose every miss, create the
   final full-public recording, check it for secrets and verify capped-day replay. At most two follow-up full-set
   evals and one recording are authorized; none has been used at this checkpoint.
6. **Deployment preparation:** finalize image digest, region/preset, durable storage, IAM, current prices,
   expiry-aware operating schedule and rollback commands. The [cost worksheet](../../deploy/nebius/cost-manifest.json)
   is a forecast, not spend or deployment approval. Keep Endpoint + Jobs; do not create resources yet.
7. **After concrete cloud approval:** execute hosted restart/storage proof, public fresh-upload smoke and real
   manual/scheduled jobs. Capture actual states, timings, reports and screenshots; restore temporary caps.
8. **Demo/release:** finish the judge walk, video assets, truthful README/SUBMISSION/FEEDBACK, ranked issues,
   exact reproduction commands and PR. Request final approval only on a concrete reviewable release.

## Kyle's parts, later

- Review each gate's evidence and accept or reject its remaining misses. Engineering authorization of the
  c05/c06 selection-policy disagreements is recorded; release acceptance remains a separate judgment.
- Review the blind labels before evaluation and adjudicate any new source/answer-key contradiction.
  Specify a configuration only when the submitted package actually selects it; leaving an option unconfirmed
  is allowed. Do not invent missing selection or assembly proof to make a case pass.
- Read provider/AI Cloud billing, account/key scope and grant expiry from private consoles. The previous
  three-credit discrepancy is unexplained; the ledger has not been adjusted. Never send keys in chat.
- Approve the final resource/IAM/storage/cost/rollback manifest and supply private account access when needed.
  The agent then carries out the approved work; Kyle need not write deployment scripts or debug storage.
- Review final claims, pitch/video and release PR, then authorize final submission through the owner account.

No cloud resources were created. G2 is open; G3–G5 remain pending. The deploy recommendation remains **no**.
