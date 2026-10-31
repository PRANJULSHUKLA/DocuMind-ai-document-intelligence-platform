"""Inspect stranded new-protocol uploads. Dry-run unless --apply is explicit."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.concurrency import run_in_threadpool
from app.db.client import mongo_client
from app.db.collections.files import files_collection
from app.services.upload_dispatch import observe_job, retry_upload
from app.utils.upload_storage import original_path, recoverable_original


async def recover(root: Path, *, apply: bool = False, minimum_age_minutes: int = 10, limit: int = 100):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minimum_age_minutes)
    query = {"upload_protocol": 1, "status": {"$in": ["saving", "queued", "failed"]},
             "enqueue_state": {"$in": ["saving", "pending", "uncertain", "not_found"]},
             "enqueue_updated_at": {"$lte": cutoff}}
    async for document in files_collection.find(query).limit(limit):
        file_id, attempt = str(document["_id"]), document["enqueue_attempt"]
        report = {"file_id": file_id, "applied": False}
        try:
            path = original_path(root, document)
            observation = await run_in_threadpool(observe_job, file_id, path, attempt)
            report["queue_state"] = observation.state
            try:
                await run_in_threadpool(recoverable_original, root, document)
            except ValueError:
                report["action"] = "original_unavailable"
                # Never purge a final original. Mark only a known non-active,
                # unchanged dispatch record failed when there is no usable file.
                if apply and observation.state in {"not_found", "terminal"}:
                    result = await files_collection.update_one(
                        {"_id": document["_id"], "upload_protocol": 1,
                         "enqueue_attempt": attempt, "status": document["status"],
                         "enqueue_updated_at": {"$lte": cutoff},
                         "$or": [{"processing_lease_until": {"$exists": False}},
                                 {"processing_lease_until": {"$lte": datetime.now(timezone.utc)}}]},
                        {"$set": {"status": "failed", "enqueue_state": "original_unavailable",
                                  "processing_error": "Original upload is unavailable. Select the original file again."}},
                    )
                    report["applied"] = bool(result.matched_count)
            else:
                report["action"] = "reconcile_or_retry"
                if apply:
                    code, result = await retry_upload(file_id, document["workspace_id"], root)
                    report.update(http_status=code, queue_state=result["enqueue_state"], applied=True)
        except Exception as exc:
            report.update(action="operator_review", error_type=type(exc).__name__)
        yield report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--minimum-age-minutes", type=int, default=10)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.minimum_age_minutes < 1 or not 1 <= args.limit <= 1000:
        parser.error("Age must be positive and limit must be between 1 and 1000.")
    # Share exactly the same configured path as the API, without importing routes.
    import os
    root = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads"))).resolve()
    try:
        async for report in recover(root, apply=args.apply, minimum_age_minutes=args.minimum_age_minutes, limit=args.limit):
            print(json.dumps(report))
    finally:
        await mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
