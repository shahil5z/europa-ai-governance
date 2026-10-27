"""Model access: a small protocol and the LangChain / OpenAI implementation.

Agents only depend on `StructuredLLM`, so tests can pass a fake and never call OpenAI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

import openai
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

from .config import Settings
from .schemas import AgentName

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Model call failed. `code` is a short machine-readable, user-safe reason."""

    code = "upstream_error"


class OutputValidationError(LLMError):
    code = "invalid_output"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class LLMTimeoutError(LLMError):
    code = "timeout"


class DeadlineExceededError(LLMError):
    code = "deadline"


class UpstreamUnavailableError(LLMError):
    code = "upstream_unavailable"


class UpstreamRateLimitedError(LLMError):
    code = "upstream_rate_limited"


class UpstreamAuthError(LLMError):
    code = "upstream_auth"


class StructuredLLM(Protocol):
    async def ainvoke(
        self,
        *,
        agent: AgentName,
        schema: type[T],
        prompt: ChatPromptTemplate,
        variables: dict[str, Any],
        timeout_s: float,
    ) -> T: ...


def summarize_validation_error(exc: ValidationError | OutputParserException) -> str:
    """Short, input-free description of a validation failure for the retry hint."""
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors(include_input=False, include_url=False)[:6]:
            loc = ".".join(str(p) for p in err["loc"]) or "output"
            parts.append(f"{loc}: {err['msg']}")
        return "; ".join(parts)[:600]
    return "output could not be parsed as the required schema"


def _default_factory(settings: Settings) -> Callable[[AgentName], BaseChatModel]:
    from langchain_openai import ChatOpenAI

    cache: dict[str, BaseChatModel] = {}

    def factory(agent: AgentName) -> BaseChatModel:
        name = settings.critic_model if agent is AgentName.CRITIC else settings.model
        if name not in cache:
            cache[name] = ChatOpenAI(
                model=name,
                api_key=settings.openai_api_key,
                temperature=settings.temperature,
                timeout=settings.call_timeout_s,
                max_retries=1,
            )
        return cache[name]

    return factory


class LangChainStructuredLLM:
    """ChatPromptTemplate | model.with_structured_output(schema), with typed errors."""

    def __init__(
        self,
        settings: Settings,
        model_factory: Callable[[AgentName], BaseChatModel] | None = None,
    ) -> None:
        self._factory = model_factory or _default_factory(settings)

    async def ainvoke(
        self,
        *,
        agent: AgentName,
        schema: type[T],
        prompt: ChatPromptTemplate,
        variables: dict[str, Any],
        timeout_s: float,
    ) -> T:
        model = self._factory(agent)
        chain = prompt | model.with_structured_output(schema, method="json_schema", strict=True)
        try:
            result = await asyncio.wait_for(chain.ainvoke(variables), timeout=timeout_s)
        except TimeoutError as exc:
            raise LLMTimeoutError("model call timed out") from exc
        except (ValidationError, OutputParserException) as exc:
            raise OutputValidationError(summarize_validation_error(exc)) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError("model call timed out") from exc
        except openai.RateLimitError as exc:
            raise UpstreamRateLimitedError("provider rate limit") from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise UpstreamAuthError("provider rejected credentials") from exc
        except openai.APIConnectionError as exc:
            raise UpstreamUnavailableError("provider unreachable") from exc
        except openai.APIError as exc:
            raise LLMError("provider error") from exc
        if not isinstance(result, schema):
            raise OutputValidationError("model returned an unexpected structure")
        return result
