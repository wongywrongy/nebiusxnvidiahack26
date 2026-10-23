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
| Bounded numeric qualifier repair, Unicode quote matching, retained bundle claims and agreeing-source citations | [Actual before/after and verification](claim-repair-20261023/README.md); same magnitude/quote/identity/selection gates; coded-driver evidence remains scoped |
| Independent lifetime-clause scope binding | [Actual two-item before/after](scope-binding-20261023/README.md); L70/MacAdam accepted, unselected driver/DLC still unknown |
| Required-gap and availability research for replacements | [Targeted evidence](replacement-research-20261023/README.md); newly discovered sources retained, unsupported active status still rejected, no complete replacement |
| Company-catalog fallback and affected legacy cache repair | [Actual product-page before/after](catalog-fallback-20261023/README.md); direct catalog requests remain valid, quote/selection gates unchanged |
| Technical-sheet revision attribution and bounded comparison wording | [Actual replay and live prompt/gate check](document-revisions-20261023/README.md); SDS revisions rejected, supported property quotes preserved |
| Public storage/IAM/cost/expiry/rollback preparation | [Unapproved bounded plan](../../deploy/nebius/rollout.pending.md); private inputs/final image/approval/hosted proof pending |
| Frozen revision-source local image | [Source `2ac6f89`, blind exclusion, mock/privacy/capped replay/restart and CI](document-revisions-20261023/README.md); predates the unit correction, unpublished, no real authority transfer or hosted proof |
| Physical-quantity units at extraction/web/release boundaries | [Synthetic before/after and actual c03/c07 check](quantity-units-20261023/README.md); missing units remain unconfirmed, no key/checklist/prompt changes |
| Persistent controller application startup and truthful uncertainty fields | [Local ext4/synthetic import/restart proof](controller-startup-20261023/README.md); existing no-wallet health/admission reused, pinned public documents seeded without overwrite, wallet never initialized; no hosted proof |

Current Python verification: **647 passed / 2 skipped**. Both [workflows for tested source `95d5a27`](quantity-units-20261023/ci.json)
pass Python/mock, presentation/build and mock browser journey/failure checks; no hosted browser proof.
Raw mock remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing replacements**,
with 46/65 claims, 8/20 web values and the unchanged selection-policy disagreements.
Actual cumulative local ledger is **$2.9516488 / 457 credits**, no holds or persistent block.
The [latest c03/c07 run](quantity-units-20261023/README.md) gets 2/2 calls/problems, 0/2 passing replacements,
zero invalidity or cap/provider warnings; two-item submitted-page/web/archive/trace consistency passes.
Four replacement investigations return found, none capped, without complete proof; no primary investigation
runs. The earlier primary rescue stays historical. The frozen `2ac6f89` image predates the unit correction;
its synthetic proof establishes no real wallet transfer, deployment or release approval.

Kyle reports account-wide **$2.13 / 421**, cutoff unspecified. Usage API observations are 415 at 07:10 UTC,
421 at 07:46 UTC and **437 at 08:53 UTC**. Local credits are 20 higher than the latest API observation;
none establishes a synchronized invoice match. Historical cached-input quantities were not retained.
Accounting remains unchanged. Public Virtual Networks/Registry rates and SecretStash preview pricing
are now resolved; public IP/egress, taxes, private IAM/quota, grant terms and approval remain open.

## Still mine to finish

1. **G2:** obtain and verify an actual complete replacement evidence bundle. Broader discovery now reaches
   Starco SLLT and Williams LT. SLLT lacks accepted MacAdam/dimming/availability evidence;
   LT now retains its unconditional L70 and MacAdam evidence; DLC/driver options
   lack selection and availability remains unconfirmed. c03 lacks complete mold/assembly/availability
   proof, and one candidate's VOC read is still unconfirmed. Broader discovery and current-source interpretation remain mine;
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
6. **Deployment preparation:** the frozen unpublished candidate predates the current unit runtime;
   finish the final validated image/registry digest, private account/IAM bindings and public-IP/egress/tax bounds.
   The [bounded draft](../../deploy/nebius/rollout.pending.md) now specifies proposed preset/storage, expiry-aware
   stop/recovery steps and resource forecasts; final identities, dates, complete allowance and approval are pending. The [cost worksheet](../../deploy/nebius/cost-manifest.json)
   is a forecast, not spend or deployment approval. Keep Endpoint + Jobs; do not create resources yet.
7. **After concrete cloud approval:** execute hosted restart/storage proof, public fresh-upload smoke and real
   manual/scheduled jobs. Capture actual states, timings, reports and screenshots; restore temporary caps.
8. **Demo/release:** finish the judge walk, video assets, truthful README/SUBMISSION/FEEDBACK, ranked issues,
   exact reproduction commands and PR. Request final approval only on a concrete reviewable release.

## Kyle's parts, later

- Decide the [replacement proposal policy](document-revisions-20261023/replacement-policy-question.md):
  require a user-selected replacement configuration, or allow a clearly labelled agent proposal whose
  exact configuration is verified from source quotes. The submitted-selection rule remains binding
  until that decision; neither option fills today's missing evidence by itself.
- Review each gate's evidence and accept or reject its remaining misses. Engineering authorization of the
  c05/c06 selection-policy disagreements is recorded; release acceptance remains a separate judgment.
- Review the blind labels before evaluation and adjudicate any new source/answer-key contradiction.
  Specify a configuration only when the submitted package actually selects it; leaving an option unconfirmed
  is allowed. Do not invent missing selection or assembly proof to make a case pass.
- Read provider/AI Cloud billing, account/key scope and grant expiry from private consoles. The latest
  account-wide reading and separate API/local totals disagree; the ledger has not been adjusted. Never send keys in chat.
- Approve the final resource/IAM/storage/cost/rollback manifest and supply private account access when needed.
  The agent then carries out the approved work; Kyle need not write deployment scripts or debug storage.
- Review final claims, pitch/video and release PR, then authorize final submission through the owner account.

No cloud resources were created. G2 is open; G3–G5 remain pending. The deploy recommendation remains **no**.
