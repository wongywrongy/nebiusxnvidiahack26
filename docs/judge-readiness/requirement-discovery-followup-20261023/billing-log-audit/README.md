# Tavily log-window audit — 2026-10-23

The documented per-request log endpoint is accessible with the existing key. This supplies stronger
billing evidence than the earlier account-wide dashboard comparison, but **does not settle the unknown
request or unblock paid work**. No wallet value, hold, campaign seed, cache or plan was changed.

[Actual comparison](reconciliation.json), [current counter response](usage-after-logs.json).

| UTC date | Local settled credits | Provider log credits | Local minus logged |
| --- | ---: | ---: | ---: |
| October 21 | 291 | 283 | 8 |
| October 22 | 67 | 66 | 1 |
| October 23 | 132 | 131 | 1 |
| Campaign period | **490** | **480** | **10** |

The full-month response contains **630 log rows / 485 credits**, below the requested limit of 10,000.
All returned masked-key suffixes are consistent with the current key; no suffix or key is published.
Five credits dated October 8 are outside this campaign's dates. Their originating application is not
established. The **10:55:11 UTC** usage GET returns **485** for both key and account, matching the monthly
log sum. The earlier five-credit local-versus-account difference mixed different date scopes: campaign
logs show a ten-credit difference from local accounting. Neither the difference nor its individual causes
is corrected by guessing. The local ceiling continues to use the conservative existing ledger.

The latest returned log is **09:52:39 UTC**. No row is returned for **10:36–10:38 UTC**, around the failed
c07 request. Absence does not supply a receipt or establish a zero charge. **One unknown credit remains
held**, separate from the 490 settled credits; raw ledger total 491 includes that hold. Dollar accounting
remains **$3.36648982 calculated locally**. Token Factory invoice reconciliation is still pending.

## Actual requests and reproduction

The [official logs reference](https://docs.tavily.com/documentation/api-reference/endpoint/logs) describes
key-filtered, most-recent-first logs. The read-only requests made here were:

1. [Same-day window](logs-observation.json): POST `/logs`, October 23 to October 23 → **400**, equal
   start/end dates rejected. The docs describe both bounds as inclusive; use a nonzero date window.
2. [Two-day retry](logs-window-retry.json): October 22–23, limit 100, key-filtered → **200**, 100 rows.
3. [Campaign window](logs-complete-window.json): October 21–23, limit 10,000, Search/Extract/Map →
   **200**, 623 rows / 480 credits.
4. [Month/all endpoints](logs-month.json): October 1–23, limit 10,000, key-filtered → **200**, 630 rows /
   485 credits, including the older five credits.
5. [Counter](usage-after-logs.json): GET `/usage` → **200**, 485 key/account credits.

Published observations retain dates, query filters, aggregates and a small redacted response sample.
Complete metadata snapshots remain ignored in `.cache/reconciliation/tavily-20261023/`, bound by the
published SHA-256 hashes. No search terms, credentials or full source content are published. The wallet
state digest stayed unchanged around every lookup. No paid search/extract/model request was made.

```bash
# Uses the existing private environment; prints numeric counters, never keys.
.venv/bin/python docs/judge-readiness/requirement-discovery-followup-20261023/billing-log-audit/reproduce.py
.venv/bin/python scripts/campaign_budget.py status
```

The [reproducer](reproduce.py) performs metadata reads only and has no payment-settlement path. Its
[offline replay check](reproducer-check.json) intercepts HTTP and replays the actual captured data,
checking counts, arithmetic and unchanged wallet state. This is separate from the actual provider calls
above. No production source changed; the existing 697-test/raw-mock source validation remains applicable.

The [billing inquiry draft](support-inquiry.txt) is ready for Kyle to send privately if needed. It has
not been sent. The unknown request needs an attributable billing confirmation before reconciliation;
the ten-credit historical campaign difference also remains open. G2, owner policy/label review, complete
release evidence and approved hosted commissioning remain incomplete.

## Unapproved release-profile correction

The production-preparation review found three different configurations: active local settings use
8,192 output tokens / concurrency 2; the rollout template still used 32,768 / 2; the last valid
targeted diagnostics used **65,536 / 1** after a 32,768-output fix was cut off. The unapproved
`deploy/nebius/controller.env.example` now proposes that measured candidate profile. Other quality/budget
limits are unchanged. [Actual parsed-profile and unchanged-local-environment check](profile-check.json).

This is a draft configuration correction, not a production default change or full-profile approval.
The exact final profile must pass complete cases/samples/reviewed blind/recording validation after
billing and gate prerequisites. The existing local image predates current code, and public delivery,
private account/IAM/funding facts, hosted restart/smoke/jobs and final owner approval remain unverified.
The original historical first-pass completion is not substituted for these current release requirements.
