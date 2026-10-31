from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.queue import workers

FILE_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def worker(store, monkeypatch, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    def save(path, **kwargs):
        Path(path).write_bytes(b"fake jpeg")
    page = SimpleNamespace(save=Mock(side_effect=save), close=Mock())
    chunks = SimpleNamespace(insert_one=AsyncMock(), delete_many=AsyncMock())
    monkeypatch.setattr(workers, "convert_from_path", Mock(return_value=[page]))
    monkeypatch.setattr(workers, "image_to_markdown", Mock(return_value="Payment due Friday."))
    monkeypatch.setattr(workers, "generate_embedding", Mock(return_value=[.1, .2]))
    monkeypatch.setattr(workers, "chunks_collection", chunks)
    return pdf, page, chunks


async def test_worker_success_has_page_metadata_and_cleanup(worker, store):
    pdf, page, chunks = worker
    await workers._process_file_async(FILE_ID, str(pdf))
    saved = chunks.insert_one.await_args.args[0]
    assert saved["page_number"] == 1
    assert saved["file_id"] == FILE_ID
    assert saved["embedding_dimension"] == 2
    assert store.update_one.await_args.args[1]["$set"]["status"] == "completed"
    assert not list(pdf.parent.glob("*_page_*.jpg"))
    page.close.assert_called()


async def test_ocr_failure_marks_failed_and_cleans_images(worker, store, monkeypatch):
    pdf, page, chunks = worker
    monkeypatch.setattr(workers, "image_to_markdown", Mock(side_effect=RuntimeError("OCR unavailable")))
    with pytest.raises(RuntimeError):
        await workers._process_file_async(FILE_ID, str(pdf))
    assert store.update_one.await_args.args[1]["$set"]["status"] == "failed"
    chunks.insert_one.assert_not_awaited()
    assert not list(pdf.parent.glob("*_page_*.jpg"))
    page.close.assert_called()


async def test_empty_ocr_is_not_completed(worker, store, monkeypatch):
    monkeypatch.setattr(workers, "image_to_markdown", Mock(return_value=""))
    with pytest.raises(RuntimeError, match="processing failed"):
        await workers._process_file_async(FILE_ID, str(worker[0]))
    assert store.update_one.await_args.args[1]["$set"]["status"] == "failed"


async def test_embedding_failure_is_visible_to_rq(worker, store, monkeypatch):
    monkeypatch.setattr(workers, "generate_embedding", Mock(return_value=[]))
    with pytest.raises(RuntimeError, match="processing failed"):
        await workers._process_file_async(FILE_ID, str(worker[0]))
    assert store.update_one.await_args.args[1]["$set"]["status"] == "failed"


async def test_duplicate_or_completed_job_is_skipped(worker, store):
    store.find_one_and_update.return_value = None
    store.find_one.return_value = {"status": "completed"}
    await workers._process_file_async(FILE_ID, str(worker[0]))
    workers.convert_from_path.assert_not_called()
    worker[2].insert_one.assert_not_awaited()


async def test_failed_run_deletes_only_its_staged_chunks(worker, store, monkeypatch):
    monkeypatch.setattr(workers, "generate_embedding", Mock(side_effect=RuntimeError("private provider output")))
    with pytest.raises(RuntimeError, match="processing failed") as error:
        await workers._process_file_async(FILE_ID, str(worker[0]))
    assert "private" not in str(error.value)
    deletion = worker[2].delete_many.await_args.args[0]
    assert deletion["file_id"] == FILE_ID
    assert isinstance(deletion["processing_run_id"], str)
    assert store.update_one.await_args.args[0]["processing_run_id"] == deletion["processing_run_id"]


async def test_published_version_matches_chunk_version(worker, store):
    await workers._process_file_async(FILE_ID, str(worker[0]))
    chunk = worker[2].insert_one.await_args.args[0]
    publication = store.update_one.await_args.args[1]["$set"]
    assert publication["active_processing_run_id"] == chunk["processing_run_id"]
    assert chunk["workspace_id"] == "test-workspace"


async def test_superseded_worker_cannot_publish(worker, store):
    store.update_one.return_value = SimpleNamespace(matched_count=0)
    with pytest.raises(RuntimeError):
        await workers._process_file_async(FILE_ID, str(worker[0]))
    assert worker[2].delete_many.await_args.args[0]["processing_run_id"]


async def test_missing_source_is_marked_failed(worker, store):
    worker[0].unlink()
    with pytest.raises(RuntimeError):
        await workers._process_file_async(FILE_ID, str(worker[0]))
    assert store.update_one.await_args.args[1]["$set"]["status"] == "failed"
