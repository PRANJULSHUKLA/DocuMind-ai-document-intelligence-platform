from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.rag_pipeline import RAGPipeline


@pytest.fixture
def pipeline(monkeypatch):
    import app.services.rag_pipeline as module
    generated = Mock(return_value=SimpleNamespace(text="Grounded answer.", candidates=[]))
    monkeypatch.setattr(module, "generate_content_with_fallback", generated)
    service = RAGPipeline()
    service.retriever = SimpleNamespace(retrieve_chunks=AsyncMock(return_value=[]))
    return service, generated


async def test_blank_question_never_retrieves_or_generates(pipeline):
    service, generated = pipeline
    with pytest.raises(ValueError):
        await service.run("file", "  ", "test-workspace")
    service.retriever.retrieve_chunks.assert_not_awaited()
    generated.assert_not_called()


async def test_empty_retrieval_abstains(pipeline):
    service, generated = pipeline
    result = await service.run("file", "What is due?", "test-workspace")
    assert result["sources"] == []
    assert result["generation_time_ms"] == 0
    generated.assert_not_called()


async def test_duplicate_evidence_is_not_repeated(pipeline):
    service, generated = pipeline
    chunk = {"text": "Payment is due Friday.", "filename": "contract.pdf", "page_number": 2, "chunk_index": 0, "score": .9}
    service.retriever.retrieve_chunks.return_value = [chunk, {**chunk, "text": " payment IS due Friday. "}]
    result = await service.run("file", "What is due?", "test-workspace")
    assert len(result["sources"]) == 1
    assert generated.call_args.kwargs["contents"].count("[SOURCE]") == 1
    assert result["answer"] == "Grounded answer."


async def test_generation_failure_propagates(pipeline):
    service, generated = pipeline
    service.retriever.retrieve_chunks.return_value = [{"text": "evidence"}]
    generated.side_effect = RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await service.run("file", "Question?", "test-workspace")


async def test_sources_only_include_evidence_inside_context_budget(pipeline, monkeypatch):
    from app.constants.rag import RAGConfig
    service, generated = pipeline
    monkeypatch.setattr(RAGConfig, "MAX_CONTEXT_LENGTH", 160)
    service.retriever.retrieve_chunks.return_value = [
        {"text": f"Evidence {i}: " + "x" * 100, "filename": "test.pdf", "page_number": i + 1, "chunk_index": i}
        for i in range(4)
    ]
    result = await service.run("file", "Question?", "test-workspace")
    context = generated.call_args.kwargs["contents"].split("<context>\n")[1].split("\n</context>")[0]
    assert len(context) <= 160
    assert context.endswith("[END SOURCE]")
    assert len(result["sources"]) == context.count("[SOURCE]") == 1


async def test_metadata_without_text_does_not_trigger_generation(pipeline):
    service, generated = pipeline
    service.retriever.retrieve_chunks.return_value = [{"text": "  ", "filename": "test.pdf"}]
    result = await service.run("file", "Question?", "test-workspace")
    assert result["sources"] == []
    generated.assert_not_called()

async def test_enriched_source_is_exact_context_excerpt(pipeline, monkeypatch):
    from app.constants.rag import RAGConfig
    from bson import ObjectId
    service, generated = pipeline
    monkeypatch.setattr(RAGConfig, 'MAX_CONTEXT_LENGTH', 180)
    chunk = {'_id': ObjectId(), 'file_id': 'file', 'filename': 'a.pdf', 'page_number': 1,
             'chunk_index': 0, 'processing_run_id': 'run', 'content_sha256': 'a' * 64,
             'text': 'Payment evidence ' * 40}
    service.retriever.retrieve_chunks.return_value = [chunk]
    result = await service.run('file', 'Question?', 'test-workspace')
    source = result['sources'][0]
    assert source['source_id'] == str(chunk['_id'])
    assert source['processing_run_id'] == 'run'
    assert source['content_sha256'] == 'a' * 64
    assert source['excerpt'] in generated.call_args.kwargs['contents']
    assert len(source['excerpt']) < len(chunk['text'])
