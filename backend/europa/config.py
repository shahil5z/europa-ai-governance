"""Runtime settings, read from environment variables only."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "gpt-4.1-mini"


def _load_dotenv(path: Path, env: dict[str, str]) -> None:
    """Minimal KEY=VALUE loader for local development. Never overrides real env."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in env:
            env[key] = value


def _int(env: Mapping[str, str], key: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(env.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def _float(env: Mapping[str, str], key: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(env.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    model: str
    critic_model: str
    temperature: float
    call_timeout_s: float
    run_deadline_s: float
    max_reassessment_rounds: int
    rate_limit_requests: int
    rate_limit_window_s: int
    global_rate_limit_requests: int
    max_concurrent_runs: int
    cors_origins: tuple[str, ...]

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        if environ is None:
            env = dict(os.environ)
            if "VERCEL" not in env:
                _load_dotenv(Path(__file__).resolve().parent.parent / ".env", env)
        else:
            env = dict(environ)
        model = env.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
        origins = env.get("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        return cls(
            openai_api_key=env.get("OPENAI_API_KEY", "").strip() or None,
            model=model,
            critic_model=env.get("OPENAI_CRITIC_MODEL", "").strip() or model,
            temperature=_float(env, "OPENAI_TEMPERATURE", 0.2, 0.0, 1.0),
            call_timeout_s=_float(env, "CALL_TIMEOUT_SECONDS", 45.0, 5.0, 120.0),
            run_deadline_s=_float(env, "RUN_DEADLINE_SECONDS", 240.0, 30.0, 280.0),
            max_reassessment_rounds=_int(env, "MAX_REASSESSMENT_ROUNDS", 1, 0, 2),
            rate_limit_requests=_int(env, "RATE_LIMIT_REQUESTS", 5, 1, 1000),
            rate_limit_window_s=_int(env, "RATE_LIMIT_WINDOW_SECONDS", 900, 10, 86400),
            global_rate_limit_requests=_int(env, "GLOBAL_RATE_LIMIT_REQUESTS", 60, 1, 100000),
            max_concurrent_runs=_int(env, "MAX_CONCURRENT_RUNS", 4, 1, 50),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )
