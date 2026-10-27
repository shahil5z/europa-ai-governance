# Deployment

One Vercel project, Git-connected to this repository, using Vercel Services (Beta). Every push to `main` builds both services and promotes the deployment to production.

| Service | Root | Runtime | Public route |
| --- | --- | --- | --- |
| `web` | `frontend/` | Next.js | `/(.*)` |
| `api` | `backend/` | Python, FastAPI entrypoint `main:app` | `/api/(.*)` |

Configured in the root `vercel.json`. The project framework preset is `services`. Python version is pinned by `backend/.python-version`. Python dependencies come from `backend/requirements.txt`.

## Environment variables

| Name | Where | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | api | Required. Stored as a sensitive environment variable, never exposed to the browser |
| `NEXT_PUBLIC_SITE_URL` | web | Canonical origin used for metadata, Open Graph, robots and sitemap |
| `OPENAI_MODEL` and the other tuning variables in `.env.example` | api | Optional |

## Streaming

`POST /api/assess` streams newline-delimited JSON. The server flushes every event, sends a heartbeat every 8 seconds, sets `Cache-Control: no-store, no-transform` and `X-Accel-Buffering: no`, and closes with an `end` event followed by 2 KB of newline padding so proxies cannot hold the final report. The browser returns as soon as it has parsed the report line and does not wait for the connection to close.

## Notes

- `images.unoptimized` is set and images are pre-sized files, so the app does not depend on the Next.js image optimizer.
- The backend deliberately has no `pyproject.toml`. Vercel prefers it over `requirements.txt` and would install nothing if it lacked a dependency list. Tool settings live in `pytest.ini` and `ruff.toml`.
- Rate limits and the concurrency cap are in memory per function instance. Set a spend limit on the OpenAI key.
- Local development does not need Vercel: run `uvicorn` and `next dev`, see the README.
