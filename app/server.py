
import os
import logging
from pathlib import Path

from bson import ObjectId
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.constants.status import FileStatus
from app.auth import Identity, current_identity
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

from app.db.collections.files import files_collection
from app.queue.q import q
from app.queue.workers import process_file


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
            {"_id": ObjectId(file_id)},
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
        )

        inserted = await files_collection.insert_one(
            record.model_dump()
        )
        file_id = str(inserted.inserted_id)

        document_dir = (UPLOAD_DIR / file_id).resolve()

        # Keep all saved files inside UPLOAD_DIR.
        if UPLOAD_DIR not in document_dir.parents:
            raise RuntimeError("Invalid upload destination.")

        document_dir.mkdir(parents=True, exist_ok=True)

        saved_path = document_dir / filename
        await run_in_threadpool(saved_path.write_bytes, content)

        await files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$set": {
                    "status": FileStatus.QUEUED,
                }
            },
        )

        # Use an explicit queue and timeout.
        await run_in_threadpool(
            q.enqueue,
            process_file,
            file_id,
            str(saved_path),
            job_timeout=1200,
        )

        return {
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "status": FileStatus.QUEUED,
            "message": "Document uploaded and queued for processing.",
        }

    except HTTPException:
        raise

    except Exception as exc:
        logger.error("Document upload failed: %s", type(exc).__name__)

        if file_id:
            await _mark_failed(file_id, "Upload setup failed. Please try again.")
        if saved_path:
            try:
                await run_in_threadpool(saved_path.unlink, missing_ok=True)
            except OSError:
                logger.warning("Could not remove failed upload: file_id=%s", file_id)

        raise HTTPException(
            status_code=500,
            detail="Upload failed. Check the backend logs.",
        ) from exc

    finally:
        await file.close()


# ---------------------------------------------------------
# Agent 1: document Q&A
# ---------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
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
        "error": (
            "Document processing failed. Please retry or contact support."
            if document.get("processing_error") else None
        ),
    }
