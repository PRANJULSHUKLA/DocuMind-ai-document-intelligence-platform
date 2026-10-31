from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.risk_engine import RiskEngine
from app.schemas.document_analysis import DocumentAnalysis
from app.schemas.workflow import WorkflowPlan
from app.services.document_analysis import DocumentAnalysisService
from app.services.workflow_service import WorkflowService

FILE_ID = "507f1f77bcf86cd799439011"


@pytest.mark.parametrize("document,error", [(None, FileNotFoundError), ({"status": "processing"}, RuntimeError), ({"status": "completed", "markdown": ""}, RuntimeError)])
async def test_analysis_rejects_missing_or_unready_documents(store, document, error):
    store.find_one.return_value = document
    service = DocumentAnalysisService()
    service.agent = SimpleNamespace(analyze=Mock())
    with pytest.raises(error):
        await service.analyze(FILE_ID, workspace_id="test-workspace")
    service.agent.analyze.assert_not_called()


async def test_analysis_merges_deterministic_risks(store):
    store.find_one.return_value = {"status": "completed", "markdown": "Payment amount: [insert here]"}
    service = DocumentAnalysisService()
    service.agent = SimpleNamespace(analyze=Mock(return_value=DocumentAnalysis(document_type="contract", executive_summary="Draft agreement")))
    result = await service.analyze(FILE_ID, workspace_id="test-workspace")
    assert any(r.source == "rule" and "[insert here]" in r.evidence for r in result.risks)


async def test_workflow_consumes_analysis(store):
    store.find_one.return_value = {"status": "completed"}
    service = WorkflowService()
    analysis = DocumentAnalysis(document_type="contract", executive_summary="Draft agreement")
    service.analysis_service = SimpleNamespace(analyze=AsyncMock(return_value=analysis))
    plan = WorkflowPlan(readiness_status="ready", overall_assessment="Review complete")
    service.agent = SimpleNamespace(analyze=Mock(return_value=plan))
    result = await service.create_plan(FILE_ID, "Review", workspace_id="test-workspace")
    assert result == plan
    assert service.agent.analyze.call_args.kwargs["analysis"] == analysis.model_dump(mode="json")


def test_rule_engine_does_not_invent_missing_fields():
    analysis = DocumentAnalysis(document_type="general", executive_summary="Complete document")
    assert RiskEngine().analyze(analysis, "Payment of 100 is due Friday.") == []
