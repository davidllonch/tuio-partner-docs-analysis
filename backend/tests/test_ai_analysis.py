"""
Unit tests for app.services.ai_analysis.run_analysis fallback logic.

Strategy:
- _call_anthropic and _call_openai are patched with AsyncMock so no real
  network calls are made.
- run_analysis is called directly — no HTTP layer involved.
- Tests verify the retry/fallback branching logic, not the AI responses.
"""

import pytest
import httpx
import anthropic as anthropic_sdk

from unittest.mock import AsyncMock, patch, call

from app.services.ai_analysis import run_analysis, _get_anthropic_client


# ---------------------------------------------------------------------------
# Fake data shared across tests
# ---------------------------------------------------------------------------

_KWARGS = dict(
    provider_name="Acme S.L.",
    provider_type="correduria_seguros",
    entity_type="PJ",
    country="ES",
    extracted_docs=[],
    anthropic_api_key="sk-ant-test",
    openai_api_key="sk-openai-test",
)


def _make_api_status_error(status_code: int) -> anthropic_sdk.APIStatusError:
    """Build a real APIStatusError with the given HTTP status code."""
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(status_code, request=req, text="error")
    return anthropic_sdk.APIStatusError("error", response=resp, body=None)


def _make_rate_limit_error() -> anthropic_sdk.RateLimitError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(429, request=req, text="rate limit")
    return anthropic_sdk.RateLimitError("rate limit", response=resp, body=None)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_succeeds_first_attempt_openai_never_called():
    """When Anthropic succeeds on the first attempt, OpenAI is never invoked."""
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
    ):
        mock_anth.return_value = ("KYC report text", "claude-sonnet-4-6")

        text, model = await run_analysis(**_KWARGS)

    assert text == "KYC report text"
    assert model == "claude-sonnet-4-6"
    mock_anth.assert_called_once()
    mock_oai.assert_not_called()


@pytest.mark.asyncio
async def test_gpt_model_routes_directly_to_openai_anthropic_never_called():
    """
    Passing a model starting with 'gpt-' must skip Anthropic entirely
    and call OpenAI directly on the first try.
    """
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
    ):
        mock_oai.return_value = ("GPT report text", "gpt-4o")

        kwargs = {**_KWARGS, "model": "gpt-4o"}
        text, model = await run_analysis(**kwargs)

    assert text == "GPT report text"
    assert model == "gpt-4o"
    mock_anth.assert_not_called()
    mock_oai.assert_called_once()


# ---------------------------------------------------------------------------
# Anthropic rate-limit fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_rate_limit_twice_falls_back_to_openai():
    """
    Two consecutive RateLimitError responses from Anthropic must trigger
    the OpenAI fallback and return the OpenAI result.
    """
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
        patch("asyncio.sleep", new_callable=AsyncMock),  # skip the 2 s pause
    ):
        mock_anth.side_effect = [
            _make_rate_limit_error(),
            _make_rate_limit_error(),
        ]
        mock_oai.return_value = ("OpenAI fallback text", "gpt-4o")

        text, model = await run_analysis(**_KWARGS)

    assert text == "OpenAI fallback text"
    assert model == "gpt-4o"
    assert mock_anth.call_count == 2
    mock_oai.assert_called_once()


# ---------------------------------------------------------------------------
# Anthropic 500 server error fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_500_error_twice_falls_back_to_openai():
    """
    Two consecutive 5xx errors from Anthropic must trigger the OpenAI fallback.
    """
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_anth.side_effect = [
            _make_api_status_error(500),
            _make_api_status_error(500),
        ]
        mock_oai.return_value = ("OpenAI fallback", "gpt-4o")

        text, model = await run_analysis(**_KWARGS)

    assert text == "OpenAI fallback"
    assert model == "gpt-4o"
    assert mock_anth.call_count == 2
    mock_oai.assert_called_once()


# ---------------------------------------------------------------------------
# Anthropic 4xx — no retry, no fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_400_client_error_raises_immediately_no_fallback():
    """
    A 4xx error (invalid request) from Anthropic must propagate immediately —
    no retry, no fallback to OpenAI.

    A 400 means our request is malformed; retrying with the same payload
    would produce the same error and waste time/money.
    """
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
    ):
        mock_anth.side_effect = _make_api_status_error(400)

        with pytest.raises(anthropic_sdk.APIStatusError):
            await run_analysis(**_KWARGS)

    mock_anth.assert_called_once()
    mock_oai.assert_not_called()


# ---------------------------------------------------------------------------
# Both providers fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_both_providers_fail_raises_runtime_error():
    """
    When both Anthropic (after retries) and OpenAI fail, a RuntimeError
    must be raised.
    """
    with (
        patch("app.services.ai_analysis._call_anthropic", new_callable=AsyncMock) as mock_anth,
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_anth.side_effect = [
            _make_rate_limit_error(),
            _make_rate_limit_error(),
        ]
        mock_oai.side_effect = Exception("OpenAI network timeout")

        with pytest.raises(RuntimeError, match="AI analysis failed"):
            await run_analysis(**_KWARGS)


@pytest.mark.asyncio
async def test_gpt_model_openai_failure_raises_runtime_error():
    """When a GPT model is requested and OpenAI fails, RuntimeError is raised."""
    with (
        patch("app.services.ai_analysis._call_openai", new_callable=AsyncMock) as mock_oai,
    ):
        mock_oai.side_effect = Exception("timeout")

        kwargs = {**_KWARGS, "model": "gpt-4o"}
        with pytest.raises(RuntimeError, match="OpenAI analysis failed"):
            await run_analysis(**kwargs)


# ---------------------------------------------------------------------------
# _get_anthropic_client caching
# ---------------------------------------------------------------------------


def test_same_api_key_returns_same_client_object():
    """
    Calling _get_anthropic_client twice with the same key must return the
    same object (module-level cache). Creating a new TCP connection on every
    request would be wasteful.
    """
    # Reset the module-level cache to ensure test isolation
    import app.services.ai_analysis as ai_mod
    ai_mod._anthropic_client = None
    ai_mod._anthropic_client_key = None

    client_a = _get_anthropic_client("sk-ant-same-key")
    client_b = _get_anthropic_client("sk-ant-same-key")
    assert client_a is client_b


def test_different_api_key_returns_new_client_object():
    """
    Calling _get_anthropic_client with a different key must create and
    return a new client (key rotation support).
    """
    import app.services.ai_analysis as ai_mod
    ai_mod._anthropic_client = None
    ai_mod._anthropic_client_key = None

    client_first = _get_anthropic_client("sk-ant-key-one")
    client_second = _get_anthropic_client("sk-ant-key-two")
    assert client_first is not client_second
