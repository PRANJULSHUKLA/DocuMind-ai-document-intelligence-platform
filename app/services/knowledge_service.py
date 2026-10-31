from app.services.rag_pipeline import RAGPipeline
from app.services.document_access import get_ready_document


class KnowledgeService:

    def __init__(self):

        self.pipeline = RAGPipeline()

    async def ask(
        self,
        file_id: str,
        question: str,
        workspace_id: str,
    ):

        await get_ready_document(file_id, workspace_id)
        response = await self.pipeline.run(
            file_id=file_id,
            question=question,
            workspace_id=workspace_id,
        )

        return response
