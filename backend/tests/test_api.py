"""HTTP API tests with an in-process ASGI client and a scripted (fake) LLM."""

from __future__ import annotations

import json

import httpx
import pytest

from europa.api import create_app
from europa.config import Settings
from europa.llm import LLMTimeoutError
from europa.schemas import MAX_DESCRIPTION_CHARS, AgentName
from tests.conftest import DESCRIPTION
from tests.fakes import ScriptedLLM, happy_script, invalid_output


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def parse(resp: httpx.Response) -> list[dict]:
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


@pytest.fixture
def app(settings):
    return create_app(settings, ScriptedLLM(happy_script()))


async def post(app, payload=None, *, raw: bytes | None = None, headers=None):
    h = {"content-type": "application/json", **(headers or {})}
    async with client_for(app) as c:
        if raw is not None:
            return await c.post("/api/assess", content=raw, headers=h)
        return await c.post("/api/assess", json=payload, headers=h)


async def test_health(app):
    async with client_for(app) as c:
        r = await c.get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["llm_configured"] is True
    assert "openai_api_key" not in json.dumps(body).lower()
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_scenarios_has_seven_editable_scenarios(app):
    async with client_for(app) as c:
        r = await c.get("/api/scenarios")
    items = r.json()["scenarios"]
    assert len(items) == 7
    assert {s["id"] for s in items} >= {
        "recruitment-screening",
        "credit-scoring",
        "medical-diagnosis-assistant",
        "customer-support",
        "education-platform",
        "smart-city-surveillance",
        "predictive-maintenance",
    }
    for s in items:
        assert 30 <= len(s["description"]) <= MAX_DESCRIPTION_CHARS


async def test_valid_assessment_streams_events_then_report(app):
    r = await post(app, {"description": DESCRIPTION})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-ndjson")
    events = parse(r)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "audit" and kinds[-1] == "report" and kinds.count("report") == 1
    report = events[-1]["report"]
    assert report["status"] == "COMPLETE"
    assert "does not constitute legal advice" in report["disclaimer"]
    assert report["consensus"]["overall_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


async def test_every_scenario_is_accepted_by_validation(app):
    async with client_for(app) as c:
        items = (await c.get("/api/scenarios")).json()["scenarios"]
    for s in items:
        from europa.schemas import AssessmentRequest

        AssessmentRequest(description=s["description"], scenario_id=s["id"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": ""},
        {"description": "   "},
        {"description": "short"},
        {"description": 5},
        {"description": DESCRIPTION, "unexpected": "x"},
        [],
        "text",
    ],
)
async def test_invalid_input_returns_422_without_internals(app, payload):
    r = await post(app, payload)
    assert r.status_code == 422, r.text
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    assert "Traceback" not in r.text and "pydantic" not in r.text.lower()


async def test_oversized_description_rejected(app):
    r = await post(app, {"description": "a" * (MAX_DESCRIPTION_CHARS + 1)})
    assert r.status_code == 422


async def test_oversized_body_rejected_with_413(app):
    r = await post(app, raw=b'{"description":"' + b"a" * 100_000 + b'"}')
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"


async def test_bad_json_and_wrong_content_type(app):
    r = await post(app, raw=b"{not json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_json"
    r = await post(app, raw=b"hello", headers={"content-type": "text/plain"})
    assert r.status_code == 415


async def test_empty_body(app):
    r = await post(app, raw=b"")
    assert r.status_code == 400


async def test_not_configured_returns_503(settings):
    s = Settings.from_env({})
    r = await post(create_app(s), {"description": DESCRIPTION})
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"


async def test_model_failure_in_every_agent_gives_failed_report_not_a_crash(settings):
    script = happy_script()
    for k in list(script):
        if k != "SUMMARY":
            script[k] = [LLMTimeoutError("timeout with secret detail sk-abc")]
    r = await post(create_app(settings, ScriptedLLM(script)), {"description": DESCRIPTION})
    assert r.status_code == 200
    last = parse(r)[-1]
    assert last["type"] == "report" and last["report"]["status"] == "FAILED"
    assert "sk-abc" not in r.text and "secret detail" not in r.text


async def test_malformed_model_output_yields_partial_report(settings):
    script = happy_script()
    script[AgentName.SECURITY] = [invalid_output()]
    r = await post(create_app(settings, ScriptedLLM(script)), {"description": DESCRIPTION})
    last = parse(r)[-1]
    assert last["report"]["status"] == "PARTIAL"
    failed = [a for a in last["report"]["agent_statuses"] if a["status"] == "FAILED"]
    assert [a["agent"] for a in failed] == ["SECURITY"]
    assert "List should have" not in json.dumps(last)  # validation detail is not exposed


async def test_rate_limit_returns_429_with_retry_after(settings):
    app = create_app(settings, ScriptedLLM(happy_script()))
    for _ in range(3):  # settings fixture allows 3 per window
        assert (await post(app, {"description": DESCRIPTION})).status_code == 200
    r = await post(app, {"description": DESCRIPTION})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    # a different client is not affected
    r2 = await post(
        app, {"description": DESCRIPTION}, headers={"x-vercel-forwarded-for": "9.9.9.9"}
    )
    assert r2.status_code == 200


async def test_invalid_requests_do_not_consume_rate_limit(settings):
    app = create_app(settings, ScriptedLLM(happy_script()))
    for _ in range(6):
        assert (await post(app, {"description": "x"})).status_code == 422
    assert (await post(app, {"description": DESCRIPTION})).status_code == 200


async def test_concurrency_cap_returns_503_busy():
    s = Settings.from_env({"OPENAI_API_KEY": "x", "MAX_CONCURRENT_RUNS": "1"})
    app = create_app(s, ScriptedLLM(happy_script(), delay=0.3))
    import asyncio

    a, b = await asyncio.gather(
        post(app, {"description": DESCRIPTION}),
        post(app, {"description": DESCRIPTION}, headers={"x-vercel-forwarded-for": "2.2.2.2"}),
    )
    assert sorted([a.status_code, b.status_code]) == [200, 503]


async def test_unexpected_exception_returns_generic_500(settings):
    app = create_app(settings, ScriptedLLM(happy_script()))

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("db password is hunter2")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/boom")
    assert r.status_code == 500
    assert "hunter2" not in r.text and "Traceback" not in r.text
    assert r.json()["error"]["code"] == "internal_error"


async def test_cors_only_allows_configured_origins(app):
    async with client_for(app) as c:
        ok = await c.options(
            "/api/assess",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        bad = await c.options(
            "/api/assess",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


async def test_openapi_and_docs_are_disabled(app):
    async with client_for(app) as c:
        assert (await c.get("/docs")).status_code == 404
        assert (await c.get("/openapi.json")).status_code == 404
