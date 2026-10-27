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

## Deploy platform and design (PLANNED, Phase 2)
Single Vercel Hobby project, Git-connected, Vercel Services (Beta): `web` (`frontend/`, nextjs) and `api` (`backend/`, `main:app`), rewrites `/api/(.*)` to `api`, everything else to `web`. Same origin, so no CORS in production. Aligned with the earlier working config in `/workspace/nexus/vercel.json` (OBSERVED, level 1).
Constraints and decisions:
- `images.unoptimized: true`: `/_next/image` is not served under Services (from the vercel-services guidance, NOT VERIFIED by a deploy).
- No `maxDuration` is set. The run is designed to finish well under 300 s; Fluid default duration is presumed 300 s (NOT VERIFIED on this account).
- Streaming pitfall inherited from an earlier project (final event buffered or dropped on Vercel, UI stuck on RUNNING): every event is flushed, heartbeats every 8 s, `no-store, no-transform`, `X-Accel-Buffering: no`, an explicit `end` event plus 2 KB padding after the terminal event; the client returns the moment the report line parses, parses a final unterminated line, and raises `report_lost` or `interrupted` if the report never arrives. Verified locally through `next start` (OBSERVED, level 3). NOT VERIFIED on Vercel.
- Rate limiting is per instance in memory and resets on cold start; use an OpenAI spend limit.

## Current task
Phase 1 (build and local verification) complete. Phase 2 (GitHub push and Vercel deploy) not started and requires explicit user approval.

## Verification status
- Backend pytest: 103 passed (MEASURED, level 2). `ruff check`: clean.
- Frontend: `eslint` clean, `tsc --noEmit` clean, vitest 30 passed, `next build` succeeds (level 2).
- Real model, backend only: 1 end-to-end run, 26.4 s, all 7 agents plus summary OK (MEASURED, level 3).
- Real model through the UI (Playwright, `next start` proxy to uvicorn): 1 run, report in 14.5 s, status COMPLETE, overall HIGH (MEASURED, level 3).
- Responsive checks at 1440, 820 and 390 px: no horizontal overflow, no console errors (level 3).
- NOT VERIFIED: Vercel Services deploy, streaming behaviour on Vercel, Hobby duration and cold start, CSP with Next inline scripts in production, screen reader behaviour (only markup reviewed), Safari and Firefox rendering.
