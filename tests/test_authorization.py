from unittest.mock import AsyncMock

from bson import ObjectId
import pytest

from app.auth import Identity
from app.services.document_analysis import DocumentAnalysisService
from app.services.knowledge_service import KnowledgeService
from app.services.workflow_service import WorkflowService

FILE_ID = "507f1f77bcf86cd799439011"
ALICE = Identity("https://issuer.test", "alice")
BOB = Identity("https://issuer.test", "bob")


@pytest.mark.parametrize("path", [f"/files/{FILE_ID}", f"/status/{FILE_ID}"])
def test_other_users_documents_are_not_found(api, store, path):
    bob_doc = {"_id": ObjectId(FILE_ID), "workspace_id": BOB.workspace_id, "status": "completed", "filename": "secret.pdf"}
    store.find_one.side_effect = lambda query: bob_doc if query.get("workspace_id") == BOB.workspace_id else None
    response = api.get(path)
    assert response.status_code == 404
    assert store.find_one.await_args.args[0]["workspace_id"] == ALICE.workspace_id


async def test_services_enforce_workspace_scope(store):
    for service, args in [
        (KnowledgeService().ask, {"question": "Question?"}),
        (DocumentAnalysisService().analyze, {}),
        (WorkflowService().create_plan, {"objective": "Review"}),
    ]:
        with pytest.raises(FileNotFoundError):
            await service(FILE_ID, workspace_id=ALICE.workspace_id, **args)
        assert store.find_one.await_args.args[0]["workspace_id"] == ALICE.workspace_id


def test_listing_is_scoped_and_allowlists_metadata(api, store):
    class Cursor:
        def sort(self, *args):
            return self
        def __aiter__(self):
            async def docs():
                yield {"_id": ObjectId(FILE_ID), "filename": "test.pdf", "status": "completed", "markdown": "CONFIDENTIAL", "embedding": [.1], "processing_error": "SECRET", "internal_path": "/private"}
            return docs()
    store.find.return_value = Cursor()
    response = api.get("/files")
    assert response.status_code == 200
    store.find.assert_called_once_with({"workspace_id": ALICE.workspace_id})
    assert response.json() == [{"_id": FILE_ID, "filename": "test.pdf", "status": "completed"}]
