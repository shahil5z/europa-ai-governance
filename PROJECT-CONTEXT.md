# PROJECT-CONTEXT: EUROPA AI GOVERNANCE

Evidence labels: VERIFIED, OBSERVED, MEASURED, INFERRED, PLANNED, NOT TESTED, NOT VERIFIED, UNKNOWN. Levels: 0 assumed, 1 code, 2 command, 3 runtime, 4 production.

## Purpose
Multi-Agent AI Governance & Risk Intelligence Platform. A user describes an AI system; specialist agents assess it in parallel; a critic and deterministic rules surface disagreements; a deterministic consensus yields a structured report. Informational only, not legal advice. Portfolio project by Shahil.

## Stack
- Backend: Python 3.13, FastAPI, LangChain (`ChatPromptTemplate`, `with_structured_output`), LangGraph (`StateGraph`, `Send`), Pydantic v2, asyncio, OpenAI (default `gpt-4.1-mini`).
- Frontend: Next.js 16 (App Router), React 19, TypeScript, Tailwind v4.
- Package managers: pip (`backend/requirements*.txt`), npm (`frontend/package-lock.json`).
- No database, stateless, no paid services besides the OpenAI key.
- Runtimes tested: box Python 3.13.5, Node 20.19.2, npm 11; target user machine Windows with Python 3.13, Node 24.

## Directories
- `backend/europa/`: `schemas.py` (contract), `graph.py` (LangGraph), `agents.py`, `llm.py` (LangChain adapter), `prompts.py`, `guardrails.py`, `disagreement.py`, `consensus.py`, `report.py`, `knowledge.py`, `scenarios.py`, `audit.py`, `service.py` (run + stream), `ratelimit.py`, `api.py`, `config.py`.
- `backend/main.py`: `app = create_app()` (Vercel entrypoint `main:app`).
- `backend/tests/`: pytest with scripted fake LLM; `dev_server.py` fake server for UI work.
- `backend/scripts/e2e.py`: opt-in real-model smoke run.
- `frontend/src/app`, `components`, `lib` (`stream.ts`, `state.ts`, `types.ts`, ...), `test/`.
- `vercel.json`: Vercel Services config (web + api).

## Architecture
`orchestrate -> specialist (Send x N) -> review (critic + deterministic detection) -> [specialist (targeted) | consensus] -> summarize -> finalize`. Per-run `RunContext` via `config["configurable"]`. Reassessment budget default 1, hard max 2. Full diagram in README.

Failure semantics: malformed output gets one retry then FAILED agent; agent failure gives PARTIAL; no specialist result gives FAILED; orchestrator failure uses a deterministic plan; critic failure gives PARTIAL; failed reassessment keeps the earlier result; summary falls back to deterministic text.

## APIs
`GET /api/health`, `GET /api/scenarios`, `POST /api/assess` (NDJSON: `audit`, `ping`, then `report` or `error`, then `end` + 2 KB newline padding). Heartbeat 8 s, run deadline 240 s. Details in README.

## Security
Key server-side only. Pydantic input limits (30 to 6000 chars, control chars stripped), body cap, in-memory per-IP rate limit (5 per 900 s), global cap 60, max 4 concurrent runs, CORS locked, security headers + CSP, generic errors, docs disabled.

## Commands
- Backend: `cd backend && python -m pytest -q && ruff check .`
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Run: `uvicorn main:app --port 8000` (backend), `npm run dev` (frontend, proxies `/api` to `BACKEND_URL`).
- Real smoke: `python backend/scripts/e2e.py` (uses the key from env, prints no secrets).

## Deployment (LIVE)
- GitHub: https://github.com/shahil5z/europa-ai-governance (public, branch `main`).
- Live: https://europa-ai-governance.vercel.app (Vercel project `europa-ai-governance`, Git-connected, framework preset `services`).
- Vercel Services (Beta): `web` (`frontend/`, nextjs) and `api` (`backend/`, `main:app`), rewrites `/api/(.*)` to `api`, the rest to `web`. Same origin, no CORS needed in production.
- Env: `OPENAI_API_KEY` (sensitive, production), `NEXT_PUBLIC_SITE_URL` (production).
- Lesson learned: a `pyproject.toml` without `dependencies` makes Vercel skip `requirements.txt`, so the API failed with `No module named 'fastapi'`. The backend has no `pyproject.toml`; pytest and ruff settings live in `pytest.ini` and `ruff.toml`.
- Streaming on Vercel (MEASURED, level 4): `application/x-ndjson`, `no-store, no-transform`, events arrive incrementally, report arrives and the UI leaves RUNNING.
- Rate limiting is per instance in memory and resets on cold start; use an OpenAI spend limit.
- `images.unoptimized: true` is kept so the app does not depend on the image optimizer.

## Current task
Released. Maintenance only.

## Verification status
- Backend pytest: 103 passed. `ruff check`: clean. Frontend: eslint, `tsc --noEmit` clean, vitest 31 passed, `next build` succeeds (level 2).
- Production (level 4): landing at 1440, 820 and 390 px has no console errors and no horizontal overflow; axe reports no violations on hero and report; canonical, Open Graph, robots and sitemap use the production URL; footer contains "Portfolio project by Shahil".
- Real model on production through the browser: 3 runs (desktop, mobile, one for the README screenshot), reports in about 15 to 17 s, status COMPLETE.
- NOT VERIFIED: Safari and Firefox rendering, screen reader behaviour (markup reviewed only), cold start latency, behaviour under sustained load.
