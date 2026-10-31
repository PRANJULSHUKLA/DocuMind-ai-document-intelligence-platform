"""Recoverable MongoDB-to-RQ dispatch. A Redis timeout is not a rejection."""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path

from bson import ObjectId
from rq.exceptions import DuplicateJobError, NoSuchJobError
from rq.job import Job
from starlette.concurrency import run_in_threadpool

from app.db.collections.files import files_collection
from app.queue.q import q
from app.queue.workers import process_file
from app.utils.upload_storage import recoverable_original

logger = logging.getLogger("documind.dispatch")
ACTIVE = {"queued", "started", "deferred", "scheduled"}
TERMINAL = {"finished", "failed", "stopped", "canceled"}


def job_id(file_id: str, attempt: int) -> str:
    if not ObjectId.is_valid(file_id) or type(attempt) is not int or attempt < 1:
        raise ValueError("Invalid processing attempt.")
    return f"documind-{file_id}-attempt-{attempt}"


@dataclass(frozen=True)
class Observation:
    state: str
    status: str | None = None


def observe_job(file_id: str, path: Path, attempt: int) -> Observation:
    try:
        # Queue.fetch_job removes queue entries on a miss. Job.fetch is read-only.
        job = Job.fetch(job_id(file_id, attempt), connection=q.connection)
        if (job.origin != q.name or job.func_name != "app.queue.workers.process_file"
                or tuple(job.args) != (file_id, str(path)) or job.kwargs != {"attempt": attempt}):
            return Observation("uncertain")
        status = job.get_status()
        status = getattr(status, "value", status)
        if status in ACTIVE:
            return Observation("confirmed", status)
        if status in TERMINAL:
            return Observation("terminal", status)
    except NoSuchJobError:
        return Observation("not_found")
    except Exception as exc:
        logger.warning("Queue reconciliation unavailable: error_type=%s", type(exc).__name__)
    return Observation("uncertain")


def enqueue_or_reconcile(file_id: str, path: Path, attempt: int) -> Observation:
    try:
        # RQ 2.10 performs unique enqueue atomically, including its queue entry.
        q.enqueue(process_file, file_id, str(path), attempt=attempt,
                  job_id=job_id(file_id, attempt), unique=True, job_timeout=1200,
                  description=f"Process document {file_id}, attempt {attempt}")
        return Observation("confirmed", "queued")
    except DuplicateJobError:
        return observe_job(file_id, path, attempt)
    except Exception as exc:
        logger.warning("Enqueue acknowledgement unavailable: error_type=%s", type(exc).__name__)
        return observe_job(file_id, path, attempt)


async def record_observation(file_id: str, attempt: int, observation: Observation) -> None:
    values = {"enqueue_state": observation.state, "enqueue_updated_at": datetime.now(timezone.utc)}
    if observation.state == "terminal":
        values.update(status="failed", processing_error="Processing stopped. Retry processing the saved document.")
    # A fast worker may already have started or completed. Never regress its state.
    await files_collection.update_one(
        {"_id": ObjectId(file_id), "enqueue_attempt": attempt, "status": "queued"},
        {"$set": values},
    )


async def dispatch(file_id: str, path: Path, attempt: int) -> Observation:
    observation = await run_in_threadpool(enqueue_or_reconcile, file_id, path, attempt)
    if observation.state == "terminal" and observation.status == "finished":
        try:
            document = await files_collection.find_one({"_id": ObjectId(file_id), "enqueue_attempt": attempt})
            if document and document.get("status") == "completed":
                observation = Observation("confirmed", "finished")
        except Exception:
            observation = Observation("uncertain")
    try:
        await record_observation(file_id, attempt, observation)
    except Exception as exc:
        # Queue acceptance cannot be undone because MongoDB lost an acknowledgement.
        logger.warning("Dispatch metadata confirmation unavailable: error_type=%s", type(exc).__name__)
    return observation


def response(file_id: str, filename: str, observation: Observation, status: str = "queued") -> tuple[int, dict]:
    code = 200 if observation.state == "confirmed" else 202
    if observation.state in {"not_found", "terminal"}:
        code = 503
    if observation.state == "terminal":
        status = "failed"
    if observation.state == "confirmed" and observation.status == "finished":
        status = "completed"
    messages = {
        "confirmed": "Document uploaded and queued for processing.",
        "uncertain": "Document saved. Queue confirmation is pending; retry processing this document if needed.",
        "not_found": "Document saved, but processing is not queued. Retry processing this saved document.",
        "terminal": "Processing stopped. Retry processing this saved document.",
    }
    return code, {"success": code < 400, "file_id": file_id, "filename": filename,
                  "status": status, "enqueue_state": observation.state,
                  "retryable": observation.state != "confirmed",
                  "message": "Document processing is already complete." if status == "completed" else messages[observation.state]}


async def retry_upload(file_id: str, workspace_id: str, root: Path) -> tuple[int, dict]:
    if not ObjectId.is_valid(file_id):
        raise ValueError("Invalid file_id.")
    document = await files_collection.find_one({"_id": ObjectId(file_id), "workspace_id": workspace_id})
    if document is None:
        raise FileNotFoundError("Document not found.")
    if document.get("status") == "completed":
        return response(file_id, document["filename"], Observation("confirmed"), "completed")
    if document.get("upload_protocol") != 1:
        raise RuntimeError("This older upload requires operator review before recovery.")
    path = await run_in_threadpool(recoverable_original, root, document)
    attempt = document["enqueue_attempt"]
    expected = job_id(file_id, attempt)
    if document.get("queue_job_id", expected) != expected:
        raise RuntimeError("Processing attempt metadata needs operator review.")
    lease = document.get("processing_lease_until")
    now = datetime.now(timezone.utc)
    if lease is not None and lease.replace(tzinfo=timezone.utc) > now:
        raise RuntimeError("Document is already processing. Wait for the current attempt.")
    observation = await run_in_threadpool(observe_job, file_id, path, attempt)
    if observation.state == "uncertain":
        return response(file_id, document["filename"], observation, document["status"])
    if observation.state == "confirmed":
        if document["status"] == "failed":
            raise RuntimeError("The previous job is still finalizing. Check its status before retrying.")
        await record_observation(file_id, attempt, observation)
        return response(file_id, document["filename"], observation, document["status"])
    # Missing unacknowledged jobs reuse the original attempt. Only a confirmed
    # terminal job or failed processing advances the fencing token.
    next_attempt = attempt + 1 if observation.state == "terminal" or document["status"] == "failed" else attempt
    prepared = await files_collection.update_one(
        {"_id": document["_id"], "workspace_id": workspace_id,
         "enqueue_attempt": attempt, "status": document["status"],
         "$or": [{"processing_lease_until": {"$exists": False}}, {"processing_lease_until": {"$lte": now}}]},
        {"$set": {"status": "queued", "enqueue_attempt": next_attempt,
                  "queue_job_id": job_id(file_id, next_attempt), "enqueue_state": "pending",
                  "enqueue_updated_at": now, "processing_error": None},
         "$unset": {"processing_lease_until": ""}},
    )
    if not prepared.matched_count:
        raise RuntimeError("Document state changed. Refresh its status before retrying.")
    observation = await dispatch(file_id, path, next_attempt)
    return response(file_id, document["filename"], observation)
