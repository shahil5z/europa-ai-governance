"""Local UI development server backed by a scripted FAKE model (no OpenAI calls).

    FAKE_MODE=disagreement|happy|partial|slow uvicorn tests.dev_server:app --port 8000
"""

import os

from europa.api import create_app
from europa.config import Settings
from europa.llm import LLMTimeoutError
from europa.schemas import AgentName, Level
from tests.fakes import (
    ScriptedLLM,
    happy_script,
    make_data,
    make_governance,
    make_oversight,
    make_risk,
    make_security,
)

mode = os.environ.get("FAKE_MODE", "disagreement")
script = happy_script()
if mode == "disagreement":
    script[AgentName.RISK] = [make_risk(Level.LOW, 0.7, "Bias risk judged limited"),
                              make_risk(Level.HIGH, 0.85, "Bias risk material after review")]
    script[AgentName.SECURITY] = [make_security(Level.HIGH, 0.8)]
    script[AgentName.DATA_GOVERNANCE] = [make_data(Level.MEDIUM)]
    script[AgentName.HUMAN_OVERSIGHT] = [make_oversight(Level.HIGH, 0.75)]
    script[AgentName.GOVERNANCE] = [make_governance(Level.HIGH, 0.8)]
elif mode == "partial":
    script[AgentName.SECURITY] = [LLMTimeoutError("fake timeout")]

settings = Settings.from_env(
    {
        "OPENAI_API_KEY": "fake-not-used",
        "RATE_LIMIT_REQUESTS": "1000",
        "MAX_REASSESSMENT_ROUNDS": "1",
    }
)
delay = float(os.environ.get("FAKE_DELAY", "2.0"))
# The scripted model is stateful: restart the server between runs to replay the script.
app = create_app(settings, ScriptedLLM(script, delay=delay))
