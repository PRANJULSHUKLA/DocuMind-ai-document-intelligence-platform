
import os
import logging
from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from app.constants.status import FileStatus
from app.schemas.file import FileSchema
from app.schemas.requests import (
    ChatRequest,
    AnalysisRequest,
    WorkflowRequest,
)
from app.schemas.responses import ChatResponse

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

UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR", "/mnt/uploads")
).resolve()

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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.app\.github\.dev",
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
    except Exception:
        logger.exception(
            "Could not mark document %s as failed.",
            file_id,
        )


def _public_file(doc: dict) -> dict:
    """Convert MongoDB fields to JSON-safe values."""
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])

    # Never expose stored vectors in document-list responses.
    doc.pop("embedding", None)

    return jsonable_encoder(doc)


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


# ---------------------------------------------------------
# Upload document
# ---------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
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
        saved_path.write_bytes(content)

        await files_collection.update_one(
            {"_id": ObjectId(file_id)},
            {
                "$set": {
                    "status": FileStatus.QUEUED,
                }
            },
        )

        # Use an explicit queue and timeout.
        q.enqueue(
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
        logger.exception("Document upload failed.")

        if file_id:
            await _mark_failed(file_id, str(exc))

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
async def chat(request: ChatRequest):
    try:
        service = KnowledgeService()

        return await service.ask(
            file_id=request.file_id,
            question=request.question,
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
        logger.exception("Chat request failed.")

        raise HTTPException(
            status_code=500,
            detail="Unable to answer the question. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# Agent 2: document intelligence and risk analysis
# ---------------------------------------------------------

@app.post("/analyze")
async def analyze_document(request: AnalysisRequest):
    try:
        service = DocumentAnalysisService()

        result = await service.analyze(
            file_id=request.file_id,
            analysis_type=request.analysis_type,
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
        logger.exception("Document analysis failed.")

        raise HTTPException(
            status_code=500,
            detail="Document analysis failed. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# Agent 3: workflow generation
# ---------------------------------------------------------

@app.post("/workflow")
async def create_workflow(request: WorkflowRequest):
    try:
        service = WorkflowService()

        result = await service.create_plan(
            file_id=request.file_id,
            objective=request.objective,
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
        logger.exception("Workflow generation failed.")

        raise HTTPException(
            status_code=500,
            detail="Workflow generation failed. Check backend logs.",
        ) from exc


# ---------------------------------------------------------
# List all documents
# ---------------------------------------------------------

@app.get("/files")
async def get_all_files():
    documents = []

    async for document in files_collection.find().sort(
        "created_at", -1
    ):
        documents.append(_public_file(document))

    return documents


# ---------------------------------------------------------
# Get a single document
# ---------------------------------------------------------

@app.get("/files/{file_id}")
async def get_file(file_id: str):
    object_id = _object_id(file_id)

    document = await files_collection.find_one(
        {"_id": object_id}
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
async def get_status(file_id: str):
    object_id = _object_id(file_id)

    document = await files_collection.find_one(
        {"_id": object_id}
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
        "error": document.get("processing_error"),
    }
