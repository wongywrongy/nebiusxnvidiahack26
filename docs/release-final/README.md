# Final release evidence — October 28, 2026

Live: https://speccheck-wongywrongys-projects.vercel.app · [Deployment](../deployment/README.md) · [Manifest](../deployment/final-deployment.json)

| File | What it shows |
| --- | --- |
| [stock-request-parity.json](stock-request-parity.json), [parity.py](parity.py) | Stock-case model requests on the deployed code match arm A's code |
| [endpoint.py](endpoint.py) | The endpoint swap: stop old, create from digest with copied settings, delete old after checks. Its raw CLI output stays local (it holds secret references) |
| [before-switch-health.json](before-switch-health.json), [after-switch-health.json](after-switch-health.json), [after-switch-origin-health.json](after-switch-origin-health.json) | Ledger unchanged across the swap; new origin serves `20261028-173729-554074` |
| [public/smoke.txt](public/smoke.txt) | No-admin smoke, run `20261028-195228-e527df` |
| `public/a`–`e` (`*.log`, `*-trace.json`, `*.png`) | Five browser journeys: off-topic upload, Try-one upload, UBC → draft → Schlage, tray scan → matrix → Review → Outcome, one product under two specs |
| [public/memo.pdf](public/memo.pdf), [public/memo.png](public/memo.png), [public/scoreboard.png](public/scoreboard.png) | Package memo printed to PDF; Scoreboard on the official run |
| `public/memo-c02.png`, `-c03`, `-c05`, `-c07` ([capture-items.mjs](capture-items.mjs)) | The four review items from the official run's memo |
| [public/check-approved.png](public/check-approved.png), [public/check-approved.json](public/check-approved.json) | Fresh Check approved now: Lithonia 2TL4 discontinued, with the manufacturer's quote |
| [public/final-health.json](public/final-health.json) | Ledger after the checks |
| [VIDEO_BRIEF.md](VIDEO_BRIEF.md) | Shot-by-shot brief for the demo video |

The public checks cost **$0.2844459 / 21 credits** (limit $2 / 100). That leaves **$72.88958832 / 5,591 credits** of the judging allowance.
