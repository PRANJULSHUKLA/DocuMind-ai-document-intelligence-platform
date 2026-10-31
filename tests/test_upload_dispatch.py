import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from bson import ObjectId
import pytest
from rq.exceptions import NoSuchJobError

from app import server
from app.auth import Identity
from app.services import upload_dispatch as dispatch

FILE_ID = "507f1f77bcf86cd799439011"
WORKSPACE = Identity("https://issuer.test", "alice").workspace_id


class MemoryFiles:
    """Minimal atomic document store for exercising API/worker state races."""
    def __init__(self):
        self.data = None

    def matches(self, query):
        if self.data is None:
            return False
        for key, value in query.items():
            if key == "$or":
                if not any(self.matches(option) for option in value):
                    return False
            elif isinstance(value, dict):
                for op, expected in value.items():
                    actual = self.data.get(key)
                    if op == "$exists" and (key in self.data) != expected:
                        return False
                    if op == "$lte" and (actual is None or actual > expected):
                        return False
                    if op == "$in" and actual not in expected:
                        return False
            elif self.data.get(key) != value:
                return False
        return True

    async def insert_one(self, document):
        self.data = {"_id": ObjectId(FILE_ID), **deepcopy(document)}
        return SimpleNamespace(inserted_id=ObjectId(FILE_ID))

    async def update_one(self, query, update):
        matched = self.matches(query)
        if matched:
            self.data.update(deepcopy(update.get("$set", {})))
            for key in update.get("$unset", {}):
                self.data.pop(key, None)
        return SimpleNamespace(matched_count=int(matched))

    async def find_one(self, query):
        return deepcopy(self.data) if self.matches(query) else None

    def find(self, query):
        selected = [deepcopy(self.data)] if self.matches(query) else []
        class Cursor:
            def limit(self, number):
                return self
            def __aiter__(self):
                async def rows():
                    for row in selected:
                        yield row
                return rows()
        return Cursor()


@pytest.fixture
def recovery(api, monkeypatch, tmp_path):
    files = MemoryFiles()
    monkeypatch.setattr(server, "files_collection", files)
    monkeypatch.setattr(dispatch, "files_collection", files)
    enqueue = Mock()
    monkeypatch.setattr(dispatch.q, "enqueue", enqueue)
    fetch = Mock(side_effect=NoSuchJobError)
    monkeypatch.setattr(dispatch.Job, "fetch", fetch)
    return SimpleNamespace(api=api, files=files, enqueue=enqueue, fetch=fetch, root=tmp_path)


def upload(recovery):
    return recovery.api.post("/upload", files={"file": ("test.pdf", b"%PDF-1.7\n")})


def job(recovery, status="queued", attempt=1):
    return SimpleNamespace(origin=dispatch.q.name, func_name="app.queue.workers.process_file",
                           args=(FILE_ID, str(recovery.root / FILE_ID / "test.pdf")),
                           kwargs={"attempt": attempt}, get_status=Mock(return_value=status))


def test_accepted_job_timeout_is_reconciled_without_deleting_pdf(recovery):
    recovery.enqueue.side_effect = TimeoutError("lost reply")
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery)
    result = upload(recovery)
    assert result.status_code == 200
    assert result.json()["enqueue_state"] == "confirmed"
    assert (recovery.root / FILE_ID / "test.pdf").read_bytes() == b"%PDF-1.7\n"
    assert recovery.files.data["status"] == "queued"
    assert recovery.enqueue.call_args.kwargs["job_id"] == dispatch.job_id(FILE_ID, 1)


def test_redis_outage_is_pending_not_failed_and_retains_original(recovery):
    recovery.enqueue.side_effect = TimeoutError()
    recovery.fetch.side_effect = ConnectionError()
    result = upload(recovery)
    assert result.status_code == 202
    assert result.json()["file_id"] == FILE_ID
    assert recovery.files.data["status"] == "queued"
    assert recovery.files.data["enqueue_state"] == "uncertain"
    assert (recovery.root / FILE_ID / "test.pdf").is_file()


def test_completed_job_with_lost_acknowledgement_is_a_success(recovery):
    def accepted(*args, **kwargs):
        recovery.files.data["status"] = "completed"
        raise TimeoutError()
    recovery.enqueue.side_effect = accepted
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "finished")
    assert upload(recovery).status_code == 200
    assert recovery.files.data["status"] == "completed"
    assert (recovery.root / FILE_ID / "test.pdf").is_file()


@pytest.mark.parametrize("advanced", ["processing", "completed", "failed"])
def test_reconciliation_does_not_regress_a_fast_worker(recovery, advanced):
    def accepted(*args, **kwargs):
        recovery.files.data.update(status=advanced, enqueue_state="confirmed")
        raise TimeoutError()
    recovery.enqueue.side_effect = accepted
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "started")
    assert upload(recovery).status_code == 200
    assert recovery.files.data["status"] == advanced
    assert recovery.files.data["enqueue_state"] == "confirmed"


def test_retry_reuses_saved_original_and_same_unconfirmed_attempt(recovery):
    recovery.enqueue.side_effect = TimeoutError()
    assert upload(recovery).status_code == 503
    recovery.enqueue.side_effect = None
    result = recovery.api.post(f"/files/{FILE_ID}/retry")
    assert result.status_code == 200
    ids = [call.kwargs["job_id"] for call in recovery.enqueue.call_args_list]
    assert ids == [dispatch.job_id(FILE_ID, 1)] * 2
    assert recovery.files.data["enqueue_attempt"] == 1


def test_retry_does_not_enqueue_again_if_original_job_exists(recovery):
    upload(recovery)
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery)
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 200
    assert recovery.enqueue.call_count == 1


def test_terminal_attempt_gets_a_new_fenced_job_id(recovery):
    upload(recovery)
    recovery.files.data["status"] = "failed"
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "failed")
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 200
    assert recovery.enqueue.call_args.kwargs["attempt"] == 2
    assert recovery.enqueue.call_args.kwargs["job_id"] == dispatch.job_id(FILE_ID, 2)


def test_retry_waits_for_failed_worker_to_finish_finalizing(recovery):
    upload(recovery)
    recovery.files.data["status"] = "failed"
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "started")
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 409
    assert recovery.enqueue.call_count == 1


def test_uncertain_retry_never_allocates_another_attempt(recovery):
    upload(recovery)
    recovery.fetch.side_effect = ConnectionError()
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 202
    assert recovery.enqueue.call_count == 1
    assert recovery.files.data["enqueue_attempt"] == 1


def test_active_lease_blocks_recovery(recovery):
    upload(recovery)
    recovery.files.data.update(status="processing", processing_lease_until=datetime.now(timezone.utc) + timedelta(minutes=1))
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 409
    assert recovery.enqueue.call_count == 1


def test_expired_failed_worker_can_be_recovered(recovery):
    upload(recovery)
    recovery.files.data.update(status="processing", processing_lease_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "failed")
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 200
    assert recovery.files.data["enqueue_attempt"] == 2


def test_completed_document_is_a_no_op(recovery):
    upload(recovery)
    recovery.files.data["status"] = "completed"
    result = recovery.api.post(f"/files/{FILE_ID}/retry")
    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    assert recovery.enqueue.call_count == 1


def test_cross_workspace_retry_does_not_inspect_or_enqueue_a_job(recovery):
    upload(recovery)
    recovery.files.data["workspace_id"] = "someone-else"
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 404
    recovery.fetch.assert_not_called()
    assert recovery.enqueue.call_count == 1


def test_missing_original_is_not_recreated_or_queued(recovery):
    upload(recovery)
    (recovery.root / FILE_ID / "test.pdf").unlink()
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 400
    assert recovery.enqueue.call_count == 1


def test_recovery_rejects_traversal_metadata(recovery):
    upload(recovery)
    recovery.files.data["filename"] = "../another.pdf"
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 400
    assert recovery.enqueue.call_count == 1


def test_recovery_rejects_symlink_escape(recovery, tmp_path):
    upload(recovery)
    original = recovery.root / FILE_ID / "test.pdf"
    original.unlink()
    elsewhere = tmp_path / "other.pdf"
    elsewhere.write_bytes(b"%PDF-1.7\n")
    original.symlink_to(elsewhere)
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 400
    assert elsewhere.read_bytes() == b"%PDF-1.7\n"
    assert recovery.enqueue.call_count == 1


def test_legacy_upload_is_not_recovered_automatically(recovery):
    upload(recovery)
    recovery.files.data.pop("upload_protocol")
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 409
    assert recovery.enqueue.call_count == 1


def test_mismatched_job_arguments_remain_uncertain(recovery):
    recovery.enqueue.side_effect = TimeoutError()
    recovery.fetch.side_effect = None
    other = job(recovery)
    other.args = ("different-file", "/other/path")
    recovery.fetch.return_value = other
    assert upload(recovery).status_code == 202
    assert recovery.files.data["enqueue_state"] == "uncertain"


async def test_concurrent_terminal_retries_allocate_only_one_next_attempt(recovery, monkeypatch):
    await recovery.files.insert_one({"filename": "test.pdf", "status": "failed", "workspace_id": WORKSPACE,
                                    "upload_protocol": 1, "upload_size_bytes": 9, "enqueue_attempt": 1})
    path = recovery.root / FILE_ID / "test.pdf"
    path.parent.mkdir()
    path.write_bytes(b"%PDF-1.7\n")
    # Both callers read attempt 1 before either can reserve the next attempt.
    gate = asyncio.Event()
    reads = 0
    original_find = recovery.files.find_one
    async def simultaneous_find(query):
        nonlocal reads
        value = await original_find(query)
        reads += 1
        if reads == 2:
            gate.set()
        await gate.wait()
        return value
    monkeypatch.setattr(recovery.files, "find_one", simultaneous_find)
    monkeypatch.setattr(dispatch, "observe_job", lambda *args: dispatch.Observation("terminal", "failed"))
    results = await asyncio.gather(*(dispatch.retry_upload(FILE_ID, WORKSPACE, recovery.root) for _ in range(2)), return_exceptions=True)
    assert sum(isinstance(result, RuntimeError) for result in results) == 1
    assert recovery.enqueue.call_count == 1
    assert recovery.files.data["enqueue_attempt"] == 2


def test_post_enqueue_metadata_failure_does_not_delete_original(recovery, monkeypatch):
    original_update = recovery.files.update_one
    async def fail_confirmation(query, update):
        if update.get("$set", {}).get("enqueue_state") == "confirmed":
            raise ConnectionError("lost MongoDB acknowledgement")
        return await original_update(query, update)
    monkeypatch.setattr(recovery.files, "update_one", fail_confirmation)
    assert upload(recovery).status_code == 200
    assert (recovery.root / FILE_ID / "test.pdf").is_file()


def test_lost_prepare_acknowledgement_can_resume_without_overwriting_state(recovery, monkeypatch):
    original_update = recovery.files.update_one
    async def lost_ack(query, update):
        result = await original_update(query, update)
        if update.get("$set", {}).get("enqueue_state") == "pending":
            raise ConnectionError("lost prepare reply")
        return result
    monkeypatch.setattr(recovery.files, "update_one", lost_ack)
    assert upload(recovery).status_code == 500
    assert recovery.files.data["status"] == "queued"
    assert (recovery.root / FILE_ID / "test.pdf").is_file()
    recovery.enqueue.assert_not_called()
    monkeypatch.setattr(recovery.files, "update_one", original_update)
    assert recovery.api.post(f"/files/{FILE_ID}/retry").status_code == 200
    assert recovery.enqueue.call_args.kwargs["attempt"] == 1


def test_confirmed_terminal_dispatch_is_distinct_from_ambiguous_acceptance(recovery):
    recovery.enqueue.side_effect = TimeoutError()
    recovery.fetch.side_effect = None
    recovery.fetch.return_value = job(recovery, "failed")
    result = upload(recovery)
    assert result.status_code == 503
    assert result.json()["enqueue_state"] == "terminal"
    assert recovery.files.data["status"] == "failed"
    assert (recovery.root / FILE_ID / "test.pdf").is_file()


def test_partial_atomic_write_cleans_only_its_temporary_file(recovery, monkeypatch):
    from app.utils import upload_storage
    monkeypatch.setattr(upload_storage.os, "fsync", Mock(side_effect=OSError("disk full")))
    assert upload(recovery).status_code == 500
    assert not list(recovery.root.rglob("*.tmp"))
    assert not (recovery.root / FILE_ID / "test.pdf").exists()
    recovery.enqueue.assert_not_called()


@pytest.mark.parametrize("apply", [False, True])
async def test_stranded_upload_recovery_has_safe_dry_run(recovery, monkeypatch, apply):
    from scripts import recover_uploads
    await recovery.files.insert_one({"filename": "test.pdf", "status": "queued", "workspace_id": WORKSPACE,
                                    "upload_protocol": 1, "upload_size_bytes": 9, "enqueue_attempt": 1,
                                    "enqueue_state": "uncertain", "enqueue_updated_at": datetime.now(timezone.utc) - timedelta(minutes=20)})
    path = recovery.root / FILE_ID / "test.pdf"
    path.parent.mkdir()
    path.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(recover_uploads, "files_collection", recovery.files)
    before = deepcopy(recovery.files.data)
    reports = [report async for report in recover_uploads.recover(recovery.root, apply=apply)]
    assert len(reports) == 1
    assert reports[0]["action"] == "reconcile_or_retry"
    assert reports[0]["applied"] == apply
    assert path.read_bytes() == b"%PDF-1.7\n"
    assert recovery.enqueue.call_count == int(apply)
    if not apply:
        assert recovery.files.data == before
    else:
        assert recovery.enqueue.call_args.kwargs["job_id"] == dispatch.job_id(FILE_ID, 1)


async def test_orphan_without_original_is_marked_failed_without_enqueue(recovery, monkeypatch):
    from scripts import recover_uploads
    await recovery.files.insert_one({"filename": "test.pdf", "status": "saving", "workspace_id": WORKSPACE,
                                    "upload_protocol": 1, "upload_size_bytes": 9, "enqueue_attempt": 1,
                                    "enqueue_state": "saving", "enqueue_updated_at": datetime.now(timezone.utc) - timedelta(minutes=20)})
    monkeypatch.setattr(recover_uploads, "files_collection", recovery.files)
    reports = [report async for report in recover_uploads.recover(recovery.root, apply=True)]
    assert reports[0]["action"] == "original_unavailable"
    assert recovery.files.data["status"] == "failed"
    recovery.enqueue.assert_not_called()


async def test_recovery_does_not_touch_legacy_or_recent_uploads(recovery, monkeypatch):
    from scripts import recover_uploads
    await recovery.files.insert_one({"filename": "test.pdf", "status": "saving", "workspace_id": WORKSPACE,
                                    "enqueue_state": "saving", "enqueue_attempt": 1,
                                    "enqueue_updated_at": datetime.now(timezone.utc) - timedelta(minutes=20)})
    monkeypatch.setattr(recover_uploads, "files_collection", recovery.files)
    assert [row async for row in recover_uploads.recover(recovery.root, apply=True)] == []
    recovery.files.data.update(upload_protocol=1, enqueue_updated_at=datetime.now(timezone.utc))
    assert [row async for row in recover_uploads.recover(recovery.root, apply=True)] == []
    recovery.enqueue.assert_not_called()
