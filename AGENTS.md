# AGENTS.md

Instructions for any coding agent working in this repository.

Project name: **EUROPA AI GOVERNANCE** (never rename it, never write it with a "//").

## Read first
- `PROJECT-CONTEXT.md`: purpose, stack, commands, decisions and verification status. Keep it current.
- `README.md`: architecture and setup.

## Working rules (rulebook conventions)
- Inspect before assuming. Plan before architecture. Make the smallest sufficient change.
- Never fabricate evidence. Label claims: VERIFIED, OBSERVED, MEASURED, INFERRED, PLANNED, NOT TESTED, NOT VERIFIED, UNKNOWN.
- Verification levels: 0 assumed, 1 code read, 2 command run, 3 runtime observed, 4 production observed.
- Keep context small: read what you need, summarise bulk output.
- Do not use the long em dash character anywhere (code, UI text, docs, comments). Use commas, colons or a plain hyphen.
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`. Review `git status` and `git diff` first.

## Secrets
- The only secret is `OPENAI_API_KEY`. Never print it, log it, or copy it into the repo.
- `.env*` (except `.env.example`) and `forblog.md` are gitignored. Keep it that way.
- Before every commit, grep the tree for `sk-` style strings and for the literal key (`grep -F`, never printing it).

## Product rules
- This is a multi-agent governance platform, not a chatbot. Agents return validated Pydantic objects.
- Never assert legal fact. Use hedged wording. Always show the disclaimer.
- The LLM writes only the executive summary and agent findings. Consensus, disagreement and status are deterministic code.
- No real OpenAI calls in tests. Use `backend/tests/fakes.py`.

## Commands
- Backend: `cd backend && python -m pytest -q && ruff check .`
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
