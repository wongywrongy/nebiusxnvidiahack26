# SpecCheck voiceover script

Read one take while `out/speccheck-guide.mp4` plays; the teleprompter band shows each line and lights each word at
150 wpm. The guide opens with a 3-second countdown; the start times below are positions in the cut (add 3 s on the
guide). Save the take as `video/audio/vo.wav` and run `./render.sh`; it finds each line in your take and fits the scenes
to your timing, so pace and small wording changes are fine. Keep the numbers and facts as written.

Target duration = words at 150 wpm + 0.35 s. 367 words; the cut is 2:31.4 at this pace.
To land at or under 2:30, read at about 152 wpm (the 5 s of lead-ins and pauses between lines stay fixed).

| Scene | What's on screen | Starts at | Target | Line |
| --- | --- | --- | --- | --- |
| S1 | Title | 0:00.3 | 9.9 s | This is SpecCheck. It checks construction submittals against the project spec and the manufacturer's live website, and tells you exactly what to send instead. |
| S2 | Context | 0:10.1 | 16.8 s | Before a product goes into a building, the subcontractor sends its data sheets, called a submittal, and someone has to check every line against the architect's spec. Miss something and it comes back revise and resubmit, and the job loses weeks. |
| S3 | Scan | 0:26.7 | 18.0 s | So I drop in the package and press Scan. NVIDIA Nemotron 3 Nano sorts the pages. Nemotron 3 Super reads every value with its exact quote. Tavily pulls each manufacturer's current documents. Both models run on Nebius Token Factory, and code makes every decision. |
| S4 | Matrix | 0:44.5 | 9.5 s | The whole package comes back as one matrix: what meets the spec, which sheets are out of date, and what's still being made. |
| S5 | Catch 1 (c02) | 0:53.8 | 13.9 s | This firestop system has a two-hour fire rating but a zero-hour temperature rating. The spec needs them to match, so SpecCheck says exactly what to send: a listed system rated two hours for both. |
| S6 | Catch 2 (c03) | 1:07.6 | 10.8 s | This sealant sheet is from 2005. The manufacturer's current sheet raised the service temperature from 120 to 180 degrees. What to send: the current data sheet. |
| S7 | Catch 3 (c07) | 1:18.2 | 15.5 s | This light fixture was approved in March 2024. One click re-checks it against the manufacturer's site. It was discontinued that June, and their notice is quoted right here. What to send: a current product that meets the spec. |
| S8 | Any spec | 1:33.6 | 14.3 s | It works on any spec. Here's a door hardware section it's never seen. Nemotron Super drafts the rules, I trim them, and a lockset is checked against them, with rules for other hardware set aside. |
| S9 | Under the hood | 1:47.8 | 17.6 s | Under the hood, every value has to be quoted from the page it came from, and code compares it to the spec. Anything unproven goes to a person, never faked. And every call is traced: which model, how many tokens, what it cost. |
| S10 | How it runs | 2:05.3 | 10.8 s | It's live, served through Vercel from a Nebius Serverless Endpoint with persistent storage. Spend is reserved before every call, and approved products are re-checked every day. |
| S11 | Memo | 2:15.9 | 8.8 s | The reviewer gets one printable memo for the whole package. On our test cases, SpecCheck caught 5 of 6 planted problems. |
| S12 | Close | 2:24.6 | 5.1 s | Models read and quote. Code decides. Try SpecCheck at the link below. |
