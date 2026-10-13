# One image, two uses:
#   the web app + API (default command), and the nightly re-check (scripts/recheck.py) as a Nebius Serverless Job.
# Build the React app, then serve it and the API from FastAPI.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY api/ api/
COPY scripts/ scripts/
# data/cases (the test set and answer key), data/fixtures (mock answers), data/requirements (reviewed checklists),
# and data/raw when it exists on the build machine: the public manufacturer and agency PDFs are not committed, so
# building from a checkout that ran scripts/fetch_docs.py bakes them in. Otherwise they are fetched at build time;
# a host that refuses leaves that case on its recorded-text excerpt (the app still runs).
COPY data/ data/
RUN python scripts/fetch_docs.py || echo "fetch_docs: some documents were not downloaded"
# Recorded live runs (scripts/record_live.py) and the last nightly re-check report, when committed.
COPY runs/ runs/
COPY --from=web /web/dist web/dist
# Defaults for a public demo. Set SPECCHECK_MODE=live, the keys and ADMIN_TOKEN in the deployment's environment.
ENV SPECCHECK_MODE=mock MOCK_STAGE_DELAY_MS=700 THINKING=off
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
