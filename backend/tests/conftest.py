import pytest

from europa.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key-not-real",
            "MAX_REASSESSMENT_ROUNDS": "1",
            "RATE_LIMIT_REQUESTS": "3",
            "RATE_LIMIT_WINDOW_SECONDS": "60",
        }
    )


DESCRIPTION = (
    "A recruitment platform that screens CVs with a language model and ranks candidates "
    "for recruiters, who review the ranked shortlist before inviting people to interview."
)
