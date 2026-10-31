from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bson import ObjectId
import pytest

from scripts import assign_legacy_workspace as migration
from app.auth import Identity

FILE_ID = ObjectId("507f1f77bcf86cd799439011")


@pytest.fixture
def migration_store(monkeypatch):
    class Cursor:
        def __init__(self):
            self.documents = [{"_id": FILE_ID}]
        def __aiter__(self):
            async def docs():
                for doc in self.documents:
                    yield doc
            return docs()
    cursor = Cursor()
    files = SimpleNamespace(find=Mock(return_value=cursor), update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)))
    chunks = SimpleNamespace(count_documents=AsyncMock(side_effect=[2, 0]), update_many=AsyncMock())
    monkeypatch.setattr(migration, "files_collection", files)
    monkeypatch.setattr(migration, "chunks_collection", chunks)
    return files, chunks, cursor


async def test_migration_dry_run_never_writes(migration_store):
    files, chunks, _ = migration_store
    result = await migration.assign("https://issuer.test", "alice")
    assert not result["applied"]
    assert result["unassigned_chunks"] == 2
    files.update_one.assert_not_awaited()
    chunks.update_many.assert_not_awaited()


async def test_migration_aborts_on_conflicting_chunk_ownership(migration_store):
    files, chunks, _ = migration_store
    chunks.count_documents.side_effect = [2, 1]
    with pytest.raises(RuntimeError, match="Conflicting"):
        await migration.assign("https://issuer.test", "alice", apply=True)
    files.update_one.assert_not_awaited()
    chunks.update_many.assert_not_awaited()


async def test_migration_does_not_claim_chunks_if_another_owner_won(migration_store):
    files, chunks, _ = migration_store
    files.update_one.return_value = SimpleNamespace(matched_count=0)
    await migration.assign("https://issuer.test", "alice", apply=True)
    chunks.update_many.assert_not_awaited()


async def test_migration_can_resume_chunk_assignment_for_same_owner(migration_store):
    files, chunks, cursor = migration_store
    target = Identity("https://issuer.test", "alice").workspace_id
    cursor.documents = [{"_id": FILE_ID, "workspace_id": target}]
    await migration.assign("https://issuer.test", "alice", apply=True)
    files.update_one.assert_not_awaited()
    assert chunks.update_many.await_args.args[1] == {"$set": {"workspace_id": target}}
