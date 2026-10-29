# Pitch cut: gate report (October 29, 2026, refinements pass)

Refinements only on `out/speccheck.mp4`: same scenes, order, voiceover and timing (every scene's length is unchanged, so
the total is still 2:29.57). Nothing was recaptured. `script/gates.py out/speccheck.mp4 <earlier cut>` writes
`out/gates/report.txt`, `out/gates/highlights.png` and `out/contact-sheet.png`.

## Take 2 (audio/vo.wav from ~/vo2.m4a, 2:36.8 raw)

`./render.sh` on Kyle's second take: **2:27.48**, −16.1 LUFS, true peak −2.8 dBTP, words clipped by a cut: none, 0 pauses
over 0.7 s, 0 banned phrases, 33 of 33 headlines readable at +12 frames, every margin as above, chips 1.4× · 1.4× · 219× ·
3.1×. The "within 1 s of 2:30" check fails by design: the new take reads 2 s faster, and the scenes follow it. The
voiceover-unchanged check does not apply to a new take. Take 1 is kept as `audio/old/vo-take1.wav`.

Room tone, rebuilt after Kyle heard faint breathing and glitches under his voice: the old bed was thousands of 10 ms
slivers of the take's quiet frames (breath tails included) butted together without fades and raised to −60 dB, about
18 dB above his room; its 10 ms level swung from −77 to −51 dB. The bed is now the take's own floor: the longest stretches
at the room's level, 100 ms clear of any breath, joined with 30 ms equal-power crossfades, at their own level (about −87 dB
RMS; 10 ms level −93 to −80 dB). Shortened pauses are spliced with 5 ms fades. Scene lengths are unchanged. Quiet moments
in the cut now sit at a median −66 dB (was −57 dB). Pause gate bound: the end of the last spoken word (it was the last
word's start + 0.5 s, which counted the end card's hold).

## Gates on out/speccheck.mp4 (refinements)

| Gate | Result |
| --- | --- |
| Duration within 1 s of 2:30 | **2:29.57** |
| Voiceover untouched | AAC stream bytes **and** decoded samples identical to the previous final (sha256) |
| Highlights inside the frame, on one row | 7 boxes, each checked on its first, middle and last frame (`out/gates/highlights.png`): matrix Decision column 2782/2815/2849, matrix Sheet out of date 2866/2986/3106, c07 dates 5042/5296/5551, c07 quote 5130/5340/5551, Any spec first rule 5903/5917/5932, deleted rule 5954/5972/5991, uploaded row 6047/6071/6096 |
| Headlines readable ≤ 0.2 s after their cue | **33 of 33**: OCR of the frame 12 frames after each cue finds the whole line |
| Side margins ≥ 96 px (context, How it runs) | context 110/110, How it runs 102/102 (non-background pixels, at 10/50/90 % of the scene, with the camera push) |
| Nothing touches the frame edge | smallest margin 13 px (matrix, bottom); every scene ≥ 1 px on all four sides |
| Banned phrases, pauses, chips, static | unchanged: 0 banned in 150 frames and on the contact sheet, 0 pauses over 0.7 s, one chip per time-lapse, longest static 0.37 s |

## Changes in this pass

- **Highlights.** One rule everywhere: the target's own box plus 8 px, clamped inside the visible crop, an 8-frame fade in and
  gone by its out cue (the old spring lingered ~0.5 s past it, which is what left boxes over the next screen). Boxes on the
  Any spec clip live in clip time: the first rule's box goes before the table jumps (6.70 s, frame differencing), the deleted
  rule's box sits on that row from when the table settles until the script click removes it (8.23 s), and the Inbox box is
  the uploaded schlage-nd.pdf row with its Check against picker (ink bounds on the clip frame at 16.8 s, inside the row's
  rules), gone before the first Schlage inset arrives. The matrix "Sheet out of date" box is now the line's ink bounds (the old
  box began 1 px inside the Product data chip above it). The quote gate, c02 and c03 show the app's own quote marks with no
  box of ours: on c02 and c03 the app's mark sits flush against the line above (0–2 px), so an 8 px box would cross text.
- **Text timing.** Every headline and overlay is a whole line: fade plus 8 px rise, fully in 12 frames after its cue, lines in
  a block 4 frames apart; exits are 8-frame fades; the end card's URL no longer types in. Scene changes are a 10-frame
  ease-in-out crossfade (same length as before). Rail nodes and the trace window no longer sit half-faded.
- **How it runs.** Five equal 312 × 300 tiles, 24 px gaps, centered (102 px margins at the camera's 1.04), entering 3 frames apart.
- **Result card.** Up from the scene's first frame; the count shows 0 and lands on 5 within 0.6 s (0 is on screen for 7 frames).
- **Pipeline rail.** The moving dot is gone; the nodes light up on their cues.
- **Context.** Both phases are one centered block: the spec and the submittal centered vertically with "Must match" centered
  over the double arrow between them; the three role boxes 440 px wide with equal 160 px gaps, the stamp and "+ weeks"
  centered over the row, the submittal travelling in a lane above the boxes (out and back), and the return arrow from
  Architect to Subcontractor ending 160 px above the bottom edge.
- **Edges.** The title's background screenshot and the Any spec clip frame now sit inside the frame; the Live scene's rail and
  clip moved in.
- The guide (`out/speccheck-guide.mp4`) was not re-rendered in this pass; its timing and script are unchanged.

# Earlier pass: final polish

Cuts: `out/speccheck.mp4` (Kyle's take, fitted), `out/speccheck-guide.mp4` (teleprompter, 150 wpm script timing, for a new take)
and `out/speccheck-silent.mp4`. 1920×1080, 60 fps, H.264 CRF 18, AAC 192k. `./render.sh` rebuilds all three and runs
`script/gates.py`, which writes `out/gates/report.txt`.

## Gates on out/speccheck.mp4

| Gate | Result |
| --- | --- |
| Duration ≤ 2:55 (target 2:10–2:30) | **2:29.57** |
| Longest fully static stretch ≤ 1.2 s | **0.40 s**; 5,697 changing frames (38 unique fps) |
| Insets: no cut text on first and last frame | 8 insets, crop-edge text pixels **0** each |
| Page, matrix and memo crops | matrix ×2, c02, c03, c07 pages: **0**. The Schlage page crop is the PDF page image's own edges (the blue banner reaches them) and the memo crop ends on the table's bottom border: checked by eye, no text cut |
| Push-ins | none left (the Any spec push-in is gone; its end is now real-screenshot close-ups) |
| One speed chip per time-lapse, outside the footage | S3 k1 1.3×, S3 k2 1.4×, S7 k4 219×, S8 k5 3.4×; each chip sits above the clip frame |
| Banned phrases (Couldn't confirm, Not confirmed, false alarm, 0 of, Ultra, No alternate) | **0** in 150 frames (OCR of one frame per second) and **0** on the contact sheet |
| Blank or loading frames | none: no frame is mostly white outside the memo and PDF pages; the scan and Review footage of the Schlage sheet is gone |
| Pauses ≤ 0.7 s between first and last word | **0** pauses over 0.7 s (silence = under −50 dB; the room-tone bed is −60 dB) |
| Loudness | **−16.0 LUFS**, true peak −3.7 dBTP (one fixed gain, `script/level.py`) |
| Words clipped by a cut | none (checked against the waveform, not whisper's word edges) |

## Fixes in this pass

- **Any spec.** k5 retaken: it opens on the UBC 08 71 00 draft form (the page gets empty room below so the section can
  sit at the top), the rule table stays at x = 0, and the last rule is deleted with a script click so the table never scrolls
  sideways. Highlights sit on the real first row and the deleted row, clamped to the table's visible box. The take ends
  with the cursor on Scan (one cached draft call, $0, 0 credits). The scene then shows the Schlage Review screenshot: the
  PDF page whole and close-ups of model ✓, Data sheet version ✓ and "25 rules for other product types". No Couldn't
  confirm rows, no "0 of 1" headers, no blank PDF.
- **Memo.** The memo's first page (project header and package matrix) fully in frame, then the app's own print output
  (Letter at 70 % scale; at 100 % the matrix columns overlap) beside it. Its matrix shows "Unconfirmed" and "Unknown" cells.
- **How it runs.** One row of five tiles: Vercel · public URL, Nebius Serverless Endpoint · runs the app, Nebius Token
  Factory · Nemotron 3 Nano + Super, Tavily · manufacturer documents, GitHub Actions · daily re-check.
- **Catch 3.** The Outcome page sits about 2 s: cropped to the heading and the Check approved now button, click, then
  the re-check as one 219× time-lapse. The status column (two "Couldn't confirm" rows) stays out.
- **Quote gate.** The C-AJ-2738 line comes from a 4× pixel-density screenshot at about 5× on screen.
- **Audio.** Cuts sit in the pause between lines at speech level (−50 dB), extended through soft attacks and decays; pauses
  inside a line over 0.6 s lose only their dead-air middle (under −70 dB); scene pads 0.35 s. A −60 dB room-tone bed
  sampled from the take runs under the whole cut.
- **Other frames with the banned phrases.** The package matrix prints "N not confirmed" under every row's rule squares, so
  S4 shows two crops of the same rows (Submittal · Documents and What to send · Decision) without the Spec rules column;
  S3's replay stops on "Scan complete" with the plain results table, before the matrix replaces it; c02 and c03 open on
  their pages (their lead clips showed the matrix and a Review header); the trace shows only its call list.

## Facts and numbers

Unchanged from the previous report: caught 5 of 6 (`scores.json`), c02 T 0 hr / F 2 hr (`results/c02.json`), c03 sheet ©
2005 with 120 °F → 180 °F (`results/c03.json`), c07 approved 2024-03-12 and discontinued 2024-06-30 (`runs/watch/latest.json`,
`results/c07.json`), c07's what-to-send line from the replayed package memo.
