import asyncio

from app.agents.workflow_agent import WorkflowAgent
from app.services.document_analysis import DocumentAnalysisService
from app.schemas.workflow import WorkflowPlan
from app.services.document_access import get_ready_document


class WorkflowService:

    def __init__(self):

        self.analysis_service = (
            DocumentAnalysisService()
        )

        self.agent = WorkflowAgent()

    async def create_plan(
        self,
        file_id: str,
        objective: str,
        workspace_id: str,
    ) -> WorkflowPlan:

        # ----------------------------------------------
        # Authorize workspace ownership and require completed processing.
        # ----------------------------------------------

        await get_ready_document(file_id, workspace_id)

        # ----------------------------------------------
        # Agent 2
        # ----------------------------------------------

        analysis = await self.analysis_service.analyze(
            file_id=file_id,
            analysis_type="contract",
            workspace_id=workspace_id,
        )

        # ----------------------------------------------
        # Agent 3
        # ----------------------------------------------

        return await asyncio.to_thread(
            self.agent.analyze,
            analysis=analysis.model_dump(
                mode="json"
            ),
            objective=objective,
        )
