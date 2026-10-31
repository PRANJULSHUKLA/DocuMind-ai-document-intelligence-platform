from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace
import pytest
from google.genai.errors import APIError
from app.errors import GenerationUnavailableError
from app.llm import gemini


def test_transient_generation_exhaustion_has_distinct_error_without_changing_retries(monkeypatch):
    generate = Mock(side_effect=APIError(429, {'error': {'code': 429, 'message': 'PRIVATE_PROVIDER_DETAIL'}}))
    monkeypatch.setattr(gemini.client.models, 'generate_content', generate)
    monkeypatch.setattr(gemini, 'MAX_RETRIES', 2)
    monkeypatch.setattr(gemini, 'FALLBACK_MODELS', [])
    monkeypatch.setattr(gemini.time, 'sleep', Mock())
    with pytest.raises(GenerationUnavailableError) as error:
        gemini.generate_content_with_fallback(model='test', contents='Question')
    assert generate.call_count == 3
    assert 'PRIVATE_PROVIDER_DETAIL' not in str(error.value)
    assert isinstance(error.value, RuntimeError)


@pytest.mark.parametrize('route,service,method,payload', [
    ('/chat', 'KnowledgeService', 'ask', {'file_id': '507f1f77bcf86cd799439011', 'question': 'Payment?'}),
    ('/analyze', 'DocumentAnalysisService', 'analyze', {'file_id': '507f1f77bcf86cd799439011'}),
    ('/workflow', 'WorkflowService', 'create_plan', {'file_id': '507f1f77bcf86cd799439011', 'objective': 'Review'}),
])
def test_generation_exhaustion_returns_503_not_document_conflict(api, monkeypatch, route, service, method, payload):
    from app import server
    mock = SimpleNamespace(**{method: AsyncMock(side_effect=GenerationUnavailableError('PRIVATE_PROVIDER_DETAIL'))})
    monkeypatch.setattr(server, service, lambda: mock)
    response = api.post(route, json=payload)
    assert response.status_code == 503
    assert 'PRIVATE_PROVIDER_DETAIL' not in response.text


@pytest.mark.parametrize('error,status', [(GenerationUnavailableError('PRIVATE_PROVIDER_DETAIL'), 503), (RuntimeError('Document changed.'), 409)])
def test_collection_distinguishes_provider_failure_from_document_conflict(api, monkeypatch, error, status):
    from app.services import collections
    monkeypatch.setattr(collections, 'ask', AsyncMock(side_effect=error))
    response = api.post('/collections/507f1f77bcf86cd799439011/chat', json={'question': 'Payment?'})
    assert response.status_code == status
    assert 'PRIVATE_PROVIDER_DETAIL' not in response.text
