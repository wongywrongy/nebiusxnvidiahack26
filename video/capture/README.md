# Captures

Everything on screen is the real app at `BASE_URL` (default: the public demo). Decisions and numbers come from the server's own
replay of the official run `20261028-173729-554074` (`replayScans` routes the app's Scan to `/api/runs/replay`; results carry
`replayed_from`, so the app labels them). Live calls are used only for the scan press (k1), "Check approved now" (k4) and the
spec draft + Schlage scan (k5). Each take logs its ledger delta to `spend.jsonl`.

`npx tsx capture/clips.ts k1…k7` records 60 fps clips (Xvfb + headed Chromium + x11grab, real cursor hidden, eased moves) to
`clips/<id>.mp4`, with `<id>.marks.json` (moments and element boxes) and `<id>.input.json` (mouse path for the drawn cursor).

| Clip | What | Calls |
| --- | --- | --- |
| k1 | Add samples, press Scan, rows start streaming; `first_decision` marks where the cut must end | live |
| k2 | Scan → the official package matrix → open c02 (saves state `replay`) | replay |
| k3 | c03: click the page tag, the PDF jumps to the quote | replay |
| k4 | Decide all, Outcome → Check approved now → c07 discontinued (saves state `outcome`) | live |
| k5 | Specs (framed on the UBC 08 71 00 draft, tables at x = 0) → draft → delete the last rule → use it → `schlage-nd.pdf`, cursor on Scan; no scan, no saved state | live (one draft call; cached, $0 on Oct 29) |
| k6 | Package memo → point-by-point alternates → print view (not in the pitch cut: its first frames show Unknown cells) | replay |
| k7 | Scoreboard (not in the pitch cut) | none |

`npx tsx capture/shots.ts [inbox|replay|outcome|memo|schlage …]` then takes the 1440×900 @2x screenshots from those saved
states (no provider calls), each with the boxes the edit zooms to, only after network idle, fonts ready and every image
decoded; a box cut at the viewport edge fails. `memo-c07` holds c07's "What to send" line exactly as the app writes it (the
live alert lists alternates instead), `memo-print` is the memo in print media and `memo.pdf` the app's print output at
70 % scale (page 1 is rendered to `shots/docs/memo-print-p1.png`). `review-c02-hi` is c02's Review at 4× pixel density for
the quote-gate close-up. The `schlage` shot still comes from state `schlage`, saved by the earlier k5 take that ran the scan
with the same edit (last rule deleted).

k5 deletes the last drafted rule and uploads the sheet as `schlage-nd.pdf` to match the release-final journey, so its scan reuses
those cached calls. A first take that deleted a middle rule got no product type back from the model and applied every rule.
