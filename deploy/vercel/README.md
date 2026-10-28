# Stable public URL (Vercel rewrite)

Vercel serves nothing itself. Every path is rewritten to the Nebius endpoint, so the app, API,
event stream and uploads all come from the origin. No functions, no build, no secrets.

## Deploy (Kyle)

```bash
cd deploy/vercel
npx vercel link            # first time: create/select the project, e.g. "speccheck"
npx vercel deploy --prod
```

Disable Deployment Protection for Production in the project settings (judges must not see a login).

## Check it

```bash
URL=https://<project>.vercel.app
curl -s $URL/api/health            # "mode":"live"
python scripts/smoke.py $URL
```

Then in a browser: a tray scan streams to Done, a 10 MB PDF upload succeeds, Review page images load.

## Repoint when the origin URL changes

1. Edit the `destination` host in `vercel.json` (keep `/$1`).
2. `npx vercel deploy --prod` from this folder.
3. Re-run the checks above. The public URL does not change.
