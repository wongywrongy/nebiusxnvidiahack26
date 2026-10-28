# Customer-feedback video delta — October 28, 2026

Superseded by the shot-by-shot [video brief](../docs/release-final/VIDEO_BRIEF.md) for the final release; the rules below still apply.

- Re-capture the real public app at https://speccheck-wongywrongys-projects.vercel.app after deployment. The earlier video on `video/pipeline` shows the previous UI.
- Scan complete now shows the compliance matrix. Magnify one real row, then open it in Review.
- End each catch on **What to send**, plus its ranked alternates or **Specify** line. Keep the PDF and source quotes visible. A possible alternate is not an acceptable replacement.
- Show **Flag for manual review** and its Outcome bucket.
- Before results, show **Package review memo**, print it and scroll one actual point-by-point alternate table. Keep live/cached/replay/unreviewed labels.
- Fresh 2x Review captures are needed for each catch. W1 screenshots are in `docs/customer-feedback/screens/`; final public evidence is in `docs/release-final/public/`.

Exact current numbers: **6/8 right calls, 5/6 problems caught, 1/2 false alarms, 0/5 passing replacements**, 0 unnecessary notes. Wrong-spec: **0 approved out of 14** (13 not applicable, 1 sent back). Source: `runs/recorded/20261028-173729-554074/scores.json`; wrong-spec run `20261028-183608-dfa1b9`. Say **0/2 false alarms** nowhere: clean case c05 is now sent back.

The 6/8, 5/6 numbers now match October 22 again; the morning 4/8, 4/6 figures are superseded. Do not describe accuracy as improved over October 22. The case gate still fails; see `docs/customer-feedback/accuracy-arms-20261028/README.md` for every changed decision. Models on screen: Nemotron 3 Nano sorts pages, Nemotron 3 Super reads data sheets and web sources and writes the result. Do not show or claim Nemotron 3 Ultra; it was tested and not adopted.

Use “suggests alternates and shows what's still unconfirmed.” Delete “finds a passing replacement.” Remove the Investigator as a headline feature: Package D triggered it on two items and resolved none. No planted-problem Investigator rescue or Nebius Serverless Job execution is proved. Show a re-check line only from the actual stored report, with its real runner and timestamp; the prepared fallback runs on GitHub Actions.

Actual Outcome line: **Re-checked by GitHub Actions · Oct 28, 07:22 UTC · 1 item, 1 flagged** (display time follows the browser timezone). Source: `docs/customer-feedback/release-20261028/public-github-recheck.json`. The fresh on-demand check is run `20261028-075230-87f8ef`; its actual discontinued alert is `docs/customer-feedback/release-20261028/public/check-approved.png`. Public memo and Scoreboard captures are in the same directory.
