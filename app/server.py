
import os
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.constants.status import FileStatus
from app.auth import Identity, current_identity
from app.errors import GenerationUnavailableError
from app.schemas.file import FileSchema
from app.schemas.requests import (
    ChatRequest,
    AnalysisRequest,
    WorkflowRequest,
)
from app.schemas.responses import ChatResponse, FileMetadataResponse

from app.services.document_analysis import DocumentAnalysisService
from app.services.workflow_service import WorkflowService
from app.services.knowledge_service import KnowledgeService
from app.services import upload_dispatch
from app.utils.upload_storage import original_path, save_original

from app.db.collections.files import files_collection
from app.queue.q import q


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

logger = logging.getLogger("documind")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parent.parent / "uploads"))).resolve()

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

if MAX_UPLOAD_MB <= 0:
    raise RuntimeError("MAX_UPLOAD_MB must be greater than zero.")


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="Enterprise AI Document Intelligence Platform",
    version="1.1.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _object_id(file_id: str) -> ObjectId:
    try:
        return ObjectId(file_id)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid file_id.",
        ) from exc


async def _mark_failed(file_id: str, message: str) -> None:
    """Best-effort status update when upload setup fails."""
    try:
        await files_collection.update_one(
            {"_id": ObjectId(file_id), "status": FileStatus.SAVING},
            {
                "$set": {
                    "status": FileStatus.FAILED,
                    "processing_error": message[:1000],
                }
            },
        )
    except Exception as exc:
        logger.error("Could not mark document failed: file_id=%s error_type=%s", file_id, type(exc).__name__)


PUBLIC_FILE_FIELDS = {
    "filename", "status", "document_type", "language", "total_pages",
    "total_chunks", "processing_time", "created_at", "processing_version",
}


def _public_file(doc: dict) -> dict:
    """Allowlist metadata so stored content and internal fields stay private."""
    result = {key: value for key, value in doc.items() if key in PUBLIC_FILE_FIELDS}
    result["_id"] = str(doc["_id"])
    return jsonable_encoder(result)


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/")
async def health():
    return {
        "status": "healthy",
        "service": "DocuMind AI",
        "version": app.version,
    }


@app.get("/session")
async def session(identity: Identity = Depends(current_identity)):
    return {"workspace_id": identity.workspace_id, "name": identity.name}


# ---------------------------------------------------------
# Upload document
# ---------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...), identity: Identity = Depends(current_identity)):
    file_id = None
    saved_path = None
    dispatch_started = False
    filename = ""

    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No filename provided.",
            )

        # Treat uploaded filenames as untrusted input.
        filename = Path(
            file.filename.replace("\\", "/")
        ).name

        if not filename or filename in {".", ".."}:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename.",
            )

        if Path(filename).suffix.lower() != ".pdf":
            raise HTTPException(
                status_code=415,
                detail="Only PDF files are supported.",
            )

        # Read at most one byte above the configured limit.
        content = await file.read(MAX_UPLOAD_BYTES + 1)

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File exceeds the {MAX_UPLOAD_MB} MB "
                    "upload limit."
                ),
            )

        # Basic signature check. PDF parsing is also validated
        # later by the worker when Poppler opens the file.
        if b"%PDF-" not in content[:1024]:
            raise HTTPException(
                status_code=415,
                detail="The uploaded file does not appear to be a valid PDF.",
            )

        record = FileSchema(
            filename=filename,
            status=FileStatus.SAVING,
            workspace_id=identity.workspace_id,
            content_sha256=hashlib.sha256(content).hexdigest(),
        )

        inserted = await files_collection.insert_one({
            **record.model_dump(), "upload_protocol": 1, "upload_size_bytes": len(content),
            "enqueue_attempt": 1, "enqueue_state": "saving",
            "enqueue_updated_at": datetime.now(timezone.utc),
        })
        file_id = str(inserted.inserted_id)

        saved_path = original_path(UPLOAD_DIR, {"_id": file_id, "filename": filename})
        await run_in_threadpool(save_original, saved_path, content)

        prepared = await files_collection.update_one(
            {"_id": ObjectId(file_id), "status": FileStatus.SAVING},
            {
                "$set": {
                    "status": FileStatus.QUEUED,
                    "queue_job_id": upload_dispatch.job_id(file_id, 1),
                    "enqueue_state": "pending",
                    "enqueue_updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if not prepared.matched_count:
            raise RuntimeError("Upload state changed before dispatch.")

        dispatch_started = True
        outcome = await upload_dispatch.dispatch(file_id, saved_path, 1)
        code, result = upload_dispatch.response(file_id, filename, outcome)
        return JSONResponse(result, status_code=code)

    except HTTPException:
        raise

    except Exception as exc:
        logger.error("Document upload failed: %s", type(exc).__name__)

        if dispatch_started:
            # An unexpected failure after dispatch must not destroy the accepted
            # job's original or overwrite a worker that already advanced.
            code, result = upload_dispatch.response(file_id, filename, upload_dispatch.Observation("uncertain"))
            return JSONResponse(result, status_code=code)
        if file_id:
            await _mark_failed(file_id, "Upload setup failed. Please try again.")
        return JSONResponse({"success": False, "file_id": file_id,
                             "detail": "Upload setup failed. Select the original again if it was not saved."}, status_code=500)

    finally:
        await file.close()


@app.post("/files/{file_id}/retry")
async def retry_saved_upload(file_id: str, identity: Identity = Depends(current_identity)):
    try:
        code, result = await upload_dispatch.retry_upload(file_id, identity.workspace_id, UPLOAD_DIR)
        return JSONResponse(result, status_code=code)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        logger.error("Upload recovery unavailable: error_type=%s", type(exc).__name__)
        raise HTTPException(503, "Recovery is temporarily unavailable. The saved document has been retained.") from None


# ---------------------------------------------------------
# Agent 1: document Q&A
# ---------------------------------------------------------

@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(request: ChatRequest, identity: Identity = Depends(current_identity)):
    try:
        service = KnowledgeService()

        return await service.ask(
            file_id=request.file_id,
            question=request.question,
            workspace_id=identity.workspace_id,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except GenerationUnavailableError:
        raise HTTPException(503, "Generation is temporarily unavailable. Please try again later.") from None

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.error("Chat request failed: %s", type(exc).__name__)

        raise HTTPException(
            status_code=500,
            detail="Unable to answer the question. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# Agent 2: document intelligence and risk analysis
# ---------------------------------------------------------

@app.post("/analyze")
async def analyze_document(request: AnalysisRequest, identity: Identity = Depends(current_identity)):
    try:
        service = DocumentAnalysisService()

        result = await service.analyze(
            file_id=request.file_id,
            analysis_type=request.analysis_type,
            workspace_id=identity.workspace_id,
        )

        return {
            "success": True,
            "file_id": request.file_id,
            "analysis": result.model_dump(mode="json"),
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except GenerationUnavailableError:
        raise HTTPException(503, "Generation is temporarily unavailable. Please try again later.") from None

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.error("Document analysis failed: %s", type(exc).__name__)

        raise HTTPException(
            status_code=500,
            detail="Document analysis failed. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# Agent 3: workflow generation
# ---------------------------------------------------------

@app.post("/workflow")
async def create_workflow(request: WorkflowRequest, identity: Identity = Depends(current_identity)):
    try:
        service = WorkflowService()

        result = await service.create_plan(
            file_id=request.file_id,
            objective=request.objective,
            workspace_id=identity.workspace_id,
        )

        return {
            "success": True,
            "file_id": request.file_id,
            "workflow": result.model_dump(mode="json"),
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except GenerationUnavailableError:
        raise HTTPException(503, "Generation is temporarily unavailable. Please try again later.") from None

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.error("Workflow generation failed: %s", type(exc).__name__)

        raise HTTPException(
            status_code=500,
            detail="Workflow generation failed. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# List all documents
# ---------------------------------------------------------

@app.get("/files", response_model=list[FileMetadataResponse], response_model_exclude_unset=True)
async def get_all_files(identity: Identity = Depends(current_identity)):
    documents = []

    async for document in files_collection.find({"workspace_id": identity.workspace_id}).sort(
        "created_at", -1
    ):
        documents.append(_public_file(document))

    return documents


# ---------------------------------------------------------
# Get a single document
# ---------------------------------------------------------

@app.get("/files/{file_id}", response_model=FileMetadataResponse, response_model_exclude_unset=True)
async def get_file(file_id: str, identity: Identity = Depends(current_identity)):
    object_id = _object_id(file_id)

    document = await files_collection.find_one(
        {"_id": object_id, "workspace_id": identity.workspace_id}
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return _public_file(document)


# ---------------------------------------------------------
# Processing status
# ---------------------------------------------------------

@app.get("/status/{file_id}")
async def get_status(file_id: str, identity: Identity = Depends(current_identity)):
    object_id = _object_id(file_id)

    document = await files_collection.find_one(
        {"_id": object_id, "workspace_id": identity.workspace_id}
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return {
        "file_id": file_id,
        "status": document.get("status", FileStatus.FAILED),
        "filename": document.get("filename"),
        "total_pages": document.get("total_pages", 0),
        "total_chunks": document.get("total_chunks", 0),
        "processing_time": document.get("processing_time", 0),
        "enqueue_state": document.get("enqueue_state"),
        "error": (
            "Document processing failed. Please retry or contact support."
            if document.get("processing_error") else None
        ),
    }


from app.routes.document_view import router as document_view_router
app.include_router(document_view_router)

from app.routes.collections import router as collections_router
app.include_router(collections_router)

from app.routes.comparison_reports import router as comparison_reports_router
app.include_router(comparison_reports_router)
