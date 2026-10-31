from types import SimpleNamespace
from unittest.mock import Mock

from google.genai.errors import APIError
import pytest

from app.llm import gemini


def test_transient_failure_is_retried_without_logging_response_content(monkeypatch, caplog):
    secret = "CONFIDENTIAL_MODEL_RESPONSE"
    response = SimpleNamespace(text="answer")
    generate = Mock(side_effect=[APIError(429, {"error": {"code": 429, "message": secret}}), response])
    monkeypatch.setattr(gemini.client.models, "generate_content", generate)
    monkeypatch.setattr(gemini.time, "sleep", Mock())
    monkeypatch.setattr(gemini, "MAX_RETRIES", 1)
    assert gemini.generate_content_with_fallback(model="models/test-model", contents="test") == response
    assert generate.call_count == 2
    assert secret not in caplog.text


def test_authentication_errors_are_not_retried_or_masked(monkeypatch):
    error = APIError(401, {"error": {"code": 401, "message": "private error"}})
    generate = Mock(side_effect=error)
    monkeypatch.setattr(gemini.client.models, "generate_content", generate)
    monkeypatch.setattr(gemini, "FALLBACK_MODELS", ["fallback-model"])
    with pytest.raises(APIError):
        gemini.generate_content_with_fallback(model="test-model", contents="test")
    assert generate.call_count == 1
