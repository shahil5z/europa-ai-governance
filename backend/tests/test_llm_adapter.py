"""LangChainStructuredLLM against a fake chat model: error mapping and prompt rendering."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import openai
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field, ValidationError

from europa import prompts
from europa.config import Settings
from europa.llm import (
    LangChainStructuredLLM,
    LLMError,
    LLMTimeoutError,
    OutputValidationError,
    UpstreamAuthError,
    UpstreamRateLimitedError,
    UpstreamUnavailableError,
)
from europa.schemas import AgentName, RiskAssessment
from tests.conftest import DESCRIPTION
from tests.fakes import make_risk


class FakeChat(BaseChatModel):
    behaviour: Any = None
    captured: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="x"))])

    def with_structured_output(self, schema, **kwargs):
        self.captured.append(kwargs)

        async def run(_input):
            if isinstance(self.behaviour, Exception):
                raise self.behaviour
            if callable(self.behaviour):
                return await self.behaviour()
            return self.behaviour

        return RunnableLambda(run)


def req_for(exc_or_value):
    fake = FakeChat(behaviour=exc_or_value, captured=[])
    llm = LangChainStructuredLLM(Settings.from_env({}), model_factory=lambda _a: fake)
    return fake, llm, prompts.prompt_for(AgentName.RISK)


def _request(response):
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return req, response


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (TimeoutError(), LLMTimeoutError),
        (openai.APITimeoutError(request=_request(None)[0]), LLMTimeoutError),
        (
            openai.RateLimitError(
                "x", response=httpx.Response(429, request=_request(None)[0]), body=None
            ),
            UpstreamRateLimitedError,
        ),
        (
            openai.AuthenticationError(
                "x", response=httpx.Response(401, request=_request(None)[0]), body=None
            ),
            UpstreamAuthError,
        ),
        (openai.APIConnectionError(request=_request(None)[0]), UpstreamUnavailableError),
        (
            openai.InternalServerError(
                "x", response=httpx.Response(500, request=_request(None)[0]), body=None
            ),
            LLMError,
        ),
    ],
)
async def test_provider_errors_are_mapped_to_safe_typed_errors(raised, expected):
    _fake, llm, prompt = req_for(raised)
    with pytest.raises(expected) as info:
        await llm.ainvoke(
            agent=AgentName.RISK,
            schema=RiskAssessment,
            prompt=prompt,
            variables=_vars(),
            timeout_s=5,
        )
    assert type(info.value).code


def _vars():
    return prompts.variables(DESCRIPTION, None, prompts.task_block("test focus"))


async def test_validation_error_becomes_output_validation_error():
    try:
        RiskAssessment.model_validate({})
    except ValidationError as exc:
        err = exc
    _fake, llm, prompt = req_for(err)
    with pytest.raises(OutputValidationError) as info:
        await llm.ainvoke(
            agent=AgentName.RISK,
            schema=RiskAssessment,
            prompt=prompt,
            variables=_vars(),
            timeout_s=5,
        )
    assert "summary" in info.value.detail  # field names only, no input echo


async def test_timeout_is_enforced():
    async def slow():
        await asyncio.sleep(2)

    _fake, llm, prompt = req_for(slow)
    with pytest.raises(LLMTimeoutError):
        await llm.ainvoke(
            agent=AgentName.RISK,
            schema=RiskAssessment,
            prompt=prompt,
            variables=_vars(),
            timeout_s=0.05,
        )


async def test_success_uses_strict_json_schema_mode():
    fake, llm, prompt = req_for(make_risk())
    out = await llm.ainvoke(
        agent=AgentName.RISK, schema=RiskAssessment, prompt=prompt, variables=_vars(), timeout_s=5
    )
    assert isinstance(out, RiskAssessment)
    assert fake.captured[0] == {"method": "json_schema", "strict": True}


async def test_wrong_structure_is_rejected():
    _fake, llm, prompt = req_for({"not": "a model"})
    with pytest.raises(OutputValidationError):
        await llm.ainvoke(
            agent=AgentName.RISK,
            schema=RiskAssessment,
            prompt=prompt,
            variables=_vars(),
            timeout_s=5,
        )
