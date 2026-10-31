"""Explicit ownership migration for legacy records. Dry-run unless --apply is passed."""
import argparse
import asyncio
import sys
from pathlib import Path

# Allow invocation from the repository root without installing this application.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import Identity
from app.db.collections.chunks import chunks_collection
from app.db.collections.files import files_collection
from app.db.client import mongo_client


async def assign(issuer: str, subject: str, apply: bool = False) -> dict:
    workspace_id = Identity(issuer, subject).workspace_id
    missing = {"$or": [{"workspace_id": {"$exists": False}}, {"workspace_id": None}]}
    # Include this owner's records so interrupted chunk assignment is resumable.
    candidates = {"$or": missing["$or"] + [{"workspace_id": workspace_id}]}
    documents = [doc async for doc in files_collection.find(candidates, {"_id": 1, "workspace_id": 1})]
    document_ids = [doc["_id"] for doc in documents]
    chunk_filter = {"file_id": {"$in": [str(value) for value in document_ids]}, **missing}
    result = {"workspace_id": workspace_id, "unassigned_documents": sum(not doc.get("workspace_id") for doc in documents), "unassigned_chunks": await chunks_collection.count_documents(chunk_filter), "applied": apply}
    if apply and document_ids:
        conflicts = await chunks_collection.count_documents({
            "file_id": {"$in": [str(value) for value in document_ids]},
            "workspace_id": {"$exists": True, "$nin": [None, workspace_id]},
        })
        if conflicts:
            raise RuntimeError("Conflicting chunk ownership; no migration applied.")
        for document in documents:
            # CAS the document before assigning chunks. Two operators cannot
            # claim one document for different owners. Interrupted work can be
            # resumed by the same owner, while existing assignments never move.
            if document.get("workspace_id") != workspace_id:
                claimed = await files_collection.update_one(
                    {"_id": document["_id"], **missing},
                    {"$set": {"workspace_id": workspace_id}},
                )
                if not claimed.matched_count:
                    continue
            await chunks_collection.update_many(
                {"file_id": str(document["_id"]), **missing},
                {"$set": {"workspace_id": workspace_id}},
            )
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", required=True, help="Exact verified issuer, including any trailing slash.")
    parser.add_argument("--subject", required=True, help="Verified subject of the intended document owner.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.issuer or not args.subject.strip():
        parser.error("Issuer and subject are required.")
    try:
        print(await assign(args.issuer, args.subject, args.apply))
    finally:
        await mongo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
