# Feedback log

Evidence gathered during the offline build on 2026-10-13. Documentation observations are **docs review only**;
fixture/respx/fake-CLI behavior is labelled separately and does not establish live API behavior. Earlier rows
without reproducible evidence from this build were removed. Add live feedback only after an observed call,
with a redacted request, response, date and reproduction steps. Never include credentials.

| Date | Product / evidence | Observation | Suggestion |
| --- | --- | --- | --- |
| 2026-10-13 | Tavily Search — docs review only; no API call | The [Search reference](https://docs.tavily.com/documentation/api-reference/endpoint/search) describes `news` around mainstream current events. Manufacturer notices also need general search. Domain preference requires a nonempty `include_domains`; omitting it returns 400 according to the docs. | Add a product-lifecycle example combining a model query, general search and preferred manufacturer domains. SpecCheck now merges general/news/notice results; respx demonstrates a general-only notice surviving the merge, without claiming live recall. |
| 2026-10-13 | Nebius CLI — docs review only; local help checked, no cloud call | The [job create reference](https://docs.nebius.com/cli/reference/ai/job/create) says asynchronous JSON is an Operation: `resource_id` is the created job, while `id` is the operation. Local CLI 0.12.289 help agrees. | Keep a create → extract resource ID → poll job example beside asynchronous output examples. The app's fake CLI regression explicitly returns different IDs. |
| 2026-10-13 | SpecCheck's Nebius integration — offline fake CLI only | `tests/test_cloud_jobs.py` exercises create/poll, duplicate launch prevention, unknown raw states, secret selectors and private-key redaction. Tests do not establish real job-state names, mount behavior or cold-start latency. | After the first real job, record redacted states and measured duration in the deployment guide; retain the documented `COMPLETED` mapping until then. |
| 2026-10-13 | SpecCheck's Nemotron/Tavily integration — offline fixtures/respx only | `tests/test_tuning.py` verifies effective task thinking in cache keys, depth-based credit accounting and quote-gate counters. Mock eval keeps 48/48 extracted claims and 19/20 web values; it catches 6/6 planted problems on eight known cases. | Use the README's one-knob comparison loop for an owner-run live evaluation. These fixture numbers validate wiring, not model accuracy or actual billed credits. |
