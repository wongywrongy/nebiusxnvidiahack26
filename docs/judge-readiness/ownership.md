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
| Separate release promotion check across cases, samples, frozen blind set and full public recording | [Offline release preflight](release-preflight-20261023/README.md); submitted-page and web quote gates replayed; no actual blind review or promotion |
| Six new source-labelled packages and a label-isolated eval runner | [Frozen draft review table](blind-20261023/README.md); six downloaded native PDFs, hashes and page quotes checked; owner review pending, no pipeline evaluation |
| Explicit private wallet export/import, interrupted-transfer recovery and approved writer-cutover tools | [Local transfer evidence](authority-transfer-20261023/README.md); synthetic wallets/mounts only, no real transfer or approval |
| Local container packaging and pinned CLI verification | [Image build evidence](image-build-20261023/README.md); 13 locked PDFs, source hash, CLI/help, mock eval and network-disabled API/assets pass; keys/private paths absent; image unpublished |

Current Python verification: **560 passed / 2 skipped**. Presentation checks and web build passed in the
preceding release-preflight checkpoint. The eight browser tests also pass in that checkpoint's GitHub CI;
no new local browser run is claimed for the backend changes below.
Raw mock remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing replacements**.
Actual cumulative local ledger is **$1.9702294 / 391 credits**, with no outstanding holds at this checkpoint.
The latest [targeted c03/c07 run](replacement-discovery-20261023/README.md) gets 2/2 calls/problems,
0/2 passing replacements and one primary Investigator recovery, with no cap/provider warnings.

## Still mine to finish

1. **G2:** obtain and verify an actual complete replacement evidence bundle. Broader discovery now reaches
   Starco SLLT and Williams LT. SLLT lacks accepted MacAdam/dimming/current-document/availability evidence;
   LT still loses its L70 bound, has unselected DLC/driver options and unconfirmed availability. c03 lacks
   complete VOC, mold and assembly proof. Bounded correction of omitted identifiers/lost bounds remains mine;
   missing source evidence or a selection must remain unconfirmed. No candidate currently passes.
2. **Cloud controller execution, after approval:** use the implemented pinned transfer/cutover tooling to
   move the actual authority and fence its old writer. The real wallet remains local and active. Authenticate
   stopped-host observations before preparing cutover approval, and prove the private filesystem, single-VM
   writer, restart, import recovery and receipt persistence on the approved host. Offline tests do not prove
   hosted durability, transport, IAM or control-plane observations.
3. **Release evidence:** assemble the actual complete cases, samples, reviewed blind set and public recording
   under the implemented promotion check. The offline check rejects the current incomplete bundle. Actual
   owner dispositions and a passing check remain pending; diagnostic recording preserves honest wrong calls.
4. **Blind review application:** apply Kyle's decisions to the six prepared draft labels, retain exact PDF/page
   evidence, and bind the approved freeze/review before evaluation. Preparation and the label-isolated runner
   are complete; label approval remains Kyle's part. Do not infer approval or run the unreviewed set.
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
