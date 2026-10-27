"""Manual end-to-end run against the REAL model. Costs a little money; run sparingly.

Usage (bash):  OPENAI_API_KEY=... python scripts/e2e.py [scenario-id]
Prints only status, timings and levels. It never prints the key or the description.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from europa.config import Settings
from europa.llm import LangChainStructuredLLM
from europa.scenarios import get_scenario
from europa.schemas import AssessmentRequest
from europa.service import stream_assessment


async def main(scenario_id: str) -> int:
    settings = Settings.from_env()
    if not settings.llm_configured:
        print("OPENAI_API_KEY is not set")
        return 2
    scenario = get_scenario(scenario_id)
    if scenario is None:
        print("unknown scenario")
        return 2
    request = AssessmentRequest(description=scenario.description, scenario_id=scenario.id)
    start = time.monotonic()
    report = None
    async for event in stream_assessment(request, settings, LangChainStructuredLLM(settings)):
        t = time.monotonic() - start
        if event["type"] == "audit":
            e = event["event"]
            print(f"{t:6.1f}s  {e['type']:<26} {e.get('agent') or '-':<16} {e.get('status') or ''}")
        elif event["type"] == "report":
            report = event["report"]
        elif event["type"] == "error":
            print("ERROR", event["error"]["code"])
            return 1
    total = time.monotonic() - start
    if report is None:
        print("no report")
        return 1
    c = report["consensus"] or {}
    print(f"\nscenario={scenario_id} status={report['status']} wall_seconds={total:.1f}")
    print(f"overall={c.get('overall_level')} confidence={c.get('overall_confidence')}")
    print(
        f"rounds_used={report['meta']['reassessment_rounds_used']} "
        f"summary_mode={report['meta']['summary_mode']}"
    )
    for s in report["agent_statuses"]:
        err = s.get("error_code") or ""
        print(f"  {s['agent']:<16} {s['status']:<9} attempts={s.get('attempts')} {err}")
    print("disagreements:", [(d["kind"], d["status"]) for d in report["disagreements"]])
    print(
        "limitations:",
        len(report["limitations"]),
        "recommendations:",
        len(report["recommendations"]),
    )
    return 0 if report["status"] in ("COMPLETE", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(
        asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "recruitment-screening"))
    )
