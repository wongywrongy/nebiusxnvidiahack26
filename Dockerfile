# One container: build the React app, then serve it and the API from FastAPI.

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
COPY data/cases/ data/cases/
COPY data/fixtures/ data/fixtures/
# The submittal and spec PDFs are public manufacturer and agency documents, not committed: download them at build
# time so Review shows real pages with highlights. A host that refuses leaves that case on its recorded-text excerpt.
COPY scripts/fetch_docs.py scripts/fetch_docs.py
RUN python scripts/fetch_docs.py || echo "fetch_docs: some documents were not downloaded"
# Recorded live runs (scripts/record_live.py): the public demo replays the newest.
COPY runs/recorded/ runs/recorded/
COPY --from=web /web/dist web/dist
ENV SPECCHECK_MODE=mock MOCK_STAGE_DELAY_MS=700
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
