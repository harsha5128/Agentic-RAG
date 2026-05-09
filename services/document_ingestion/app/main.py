"""
Document Ingestion Service - FastAPI Application

Event-driven architecture: S3 object-created event -> ingestion normalization
-> SQS parsing job. Multipart UploadFile ingestion is intentionally removed.
"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import Any, Dict

from fastapi import Body, FastAPI, HTTPException

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.base_service import BaseService
from common.config import settings
from common.exceptions import DocumentIngestionError
from common.observability import get_logger

from .core.ingestion_service import DocumentIngestionServiceCore

logger = get_logger(__name__)


class DocumentIngestionService(BaseService):
    """
    Production-grade document ingestion service.

    Notes:
        Custom ingestion logic lives in DocumentIngestionServiceCore so the HTTP
        layer stays thin. The core code is kept explicit for learning and future
        replacement with managed event consumers if desired.
    """

    def __init__(self):
        super().__init__("document-ingestion-service")
        self.core = None

    async def _initialize_dependencies(self) -> None:
        self.core = DocumentIngestionServiceCore(self)
        self.register_dependency("s3", lambda: self._check_s3_health())
        self.register_dependency("sqs", lambda: self._check_sqs_health())
        self.register_dependency("mongodb", lambda: self._check_mongodb_health())

    async def _check_s3_health(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
            return True
        except Exception as e:
            logger.error(f"S3 health check failed: {str(e)}")
            return False

    async def _check_sqs_health(self) -> bool:
        try:
            if not settings.AWS_SQS_QUEUE_URL:
                return False
            self.sqs_client.get_queue_attributes(
                QueueUrl=settings.AWS_SQS_QUEUE_URL,
                AttributeNames=["All"],
            )
            return True
        except Exception as e:
            logger.error(f"SQS health check failed: {str(e)}")
            return False

    async def _check_mongodb_health(self) -> bool:
        try:
            await self.mongodb_db.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")
            return False

    async def process_s3_event(self, event: Dict[str, Any]) -> list:
        if not self.core:
            raise RuntimeError("Document ingestion service is not initialized")
        return await self.core.process_s3_event(event)


service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    service = DocumentIngestionService()
    await service.initialize()
    logger.info("Document Ingestion Service started")
    yield
    await service.close()
    logger.info("Document Ingestion Service shutdown")


app = FastAPI(
    title="Document Ingestion Service",
    description="Event-driven document ingestion via S3 and SQS",
    version="2.0.0",
    lifespan=lifespan,
)


async def _process_ingestion_event(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        documents = await service.process_s3_event(event)
        return {
            "status": "success",
            "documents_ingested": len(documents),
            "documents": [doc.model_dump() for doc in documents],
        }
    except DocumentIngestionError as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})


@app.post("/ingest")
async def ingest_documents(event: Dict[str, Any] = Body(...)):
    """Event-compatible ingestion endpoint retained as an internal alias."""
    return await _process_ingestion_event(event)


@app.post("/s3-events")
async def ingest_s3_events(event: Dict[str, Any] = Body(...)):
    """Preferred endpoint for S3 object-created event payloads."""
    return await _process_ingestion_event(event)


@app.get("/health")
async def health_check():
    return await service.check_health()


@app.get("/ready")
async def readiness():
    return await service.readiness_probe()


@app.get("/live")
async def liveness():
    return await service.liveness_probe()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
