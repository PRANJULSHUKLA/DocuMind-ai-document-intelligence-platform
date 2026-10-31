"""Shared workspace authorization and document readiness checks."""
from bson import ObjectId

from app.db.collections.files import files_collection


async def get_ready_document(file_id: str, workspace_id: str) -> dict:
    if not ObjectId.is_valid(file_id):
        raise ValueError("Invalid file_id.")
    if not workspace_id:
        raise ValueError("A workspace is required.")
    document = await files_collection.find_one({"_id": ObjectId(file_id), "workspace_id": workspace_id})
    if document is None:
        raise FileNotFoundError("Document not found.")
    if document.get("status") != "completed":
        raise RuntimeError("Document is not ready. Wait for processing to complete.")
    return document
