# Validated-source local image — 2026-10-23

This unpublished image freezes **`061cf9d2fcb4eb68729eb2961f6f4a8758e24e55`**, runtime
`3480e5d073f7a58d7fae7317cac2c0a83a3dc880b45e3709e2bec7e9f07f0b45`, matching the
[657-test/current two-item live checkpoint](../README.md). It excludes the newer uncommitted status-timing
work observed in the shared checkout. It is not final release approval or evidence for that newer code.

Local tag `speccheck:validated-source-local`, image/index ID
`sha256:df552ebeb449d0a174f8493fc7fd72f6a6c597794b69e5ede1b969cc14b084f7`.
[Identity/build metadata](identity.json) pins the isolated context and actual build-log hash. The context
was extracted with `git archive` and received only the 13 hash-verified public PDFs; no real environment,
wallet, cache, uploads or blind inputs were copied. Dependency and frontend layers were cached.

[Actual runtime checks](runtime-checks.json) establish the matching code, reviewed checklists/input hashes,
exact document inventory and false key-presence booleans. Required native-PDF preflight reproduces every
row of the linked reference report; the canonical JSON hash binds that comparison. The existing synthetic
unit response is rejected at extraction, web and release boundaries and remains unverified.
[Image mock output](mock.json) preserves **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes**,
zero invalid items and expected exit 1 for the disclosed raw-key disagreements.

A private-stdin [secret scan](secret-scan.json) finds no configured key/admin strings in **8,562 regular
image files**. Virtual filesystems, symlinks and deleted layers are outside this scan.

The existing isolated synthetic reproducer ran with only its pinned image constant changed;
[script identity](reproducer.json), [actual results](capped-replay-restart.json). With no real credential
environment/authority mounted, no public ports and Docker networking disabled, it proves:

- Startup creates no wallet; a new synthetic import is explicit.
- Two container/process restarts preserve synthetic authority, app markers and replayed results.
- The historical live scoreboard is served; explicit replay returns 10 recorded results.
- All eight public items replay at a synthetic zero day cap; fresh re-check returns HTTP 429.

The proof container was removed. The private temporary context/synthetic directory remains for inspection.
No provider request, image publication, cloud resource or real authority transfer occurs. The actual
local accounting after these checks is **$3.36648982 / 490 credits**, with no holds;
[observed campaign and daily mirror](accounting-after.json). This does not prove hosted storage/reboot/IAM,
fresh public-upload behavior or a current full-set evaluation. G2 and later gates remain open.

Reproduction: archive the pinned commit into a new temporary directory, copy only PDFs whose hashes
match that archive's `data/documents.lock.json`, then build the existing Dockerfile there. Run the
required-PDF command, existing unit reproducer and mock evaluation with `--network none`; use the
[existing synthetic reproducer](../../preproduction-packaging-20261023/reproduce.py) with the inspected
local image ID. Preserve the original cache/wallet and do not incorporate unreviewed shared changes.
The permanent environment is untouched. A final image must bind the final validated source/configuration
and packaged inputs after the remaining gate decisions.
