"""
Document Ingestion Service
Handles S3 object-created events and publishes document ingestion messages
"""

from fastapi import Body, FastAPI, HTTPException
from contextlib import asynccontextmanager
import json
import uuid
import boto3
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import unquote_plus
import sys
from pathlib import Path

# Add parent to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import Document, DocumentStatus, DocumentType

logger = get_logger(__name__)


class DocumentIngestionService:
    """Service for normalizing S3 object-created events into ingestion jobs"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.sqs_client = boto3.client(
            'sqs',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    
    async def ingest_s3_event(self, event: Dict[str, Any]) -> List[Document]:
        """
        Ingest documents from S3 event notifications and publish to SQS.
        
        Args:
            event: AWS S3 event notification payload
        
        Returns:
            Document objects created from S3 event records
        """
        try:
            records = self._extract_s3_records(event)
            if not records:
                raise HTTPException(status_code=400, detail="No S3 records found in event")

            documents = []
            for record in records:
                if not record.get("eventName", "").startswith("ObjectCreated:"):
                    logger.info(f"Skipping non-create S3 event: {record.get('eventName')}")
                    continue

                bucket = record["s3"]["bucket"]["name"]
                key = unquote_plus(record["s3"]["object"]["key"])
                size_bytes = record["s3"]["object"].get("size")
                document = self._build_document(bucket, key, record, size_bytes)
                self._publish_ingestion_message(document, record)
                documents.append(document)

            logger.info(f"Ingested {len(documents)} document event(s) from S3")
            return documents
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error ingesting S3 event: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def _extract_s3_records(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return S3 records from direct, SQS-wrapped, or SNS-wrapped events."""
        records = event.get("Records", [])
        s3_records = []

        for record in records:
            if "s3" in record:
                s3_records.append(record)
                continue

            sqs_body = record.get("body")
            if sqs_body:
                nested_event = json.loads(sqs_body)
                s3_records.extend(self._extract_s3_records(nested_event))
                continue

            sns_message = record.get("Sns", {}).get("Message")
            if sns_message:
                nested_event = json.loads(sns_message)
                s3_records.extend(self._extract_s3_records(nested_event))

        return s3_records

    def _build_document(
        self,
        bucket: str,
        key: str,
        record: Dict[str, Any],
        size_bytes: Optional[int],
    ) -> Document:
        file_name = Path(key).name
        if not file_name:
            raise HTTPException(status_code=400, detail=f"S3 object key is not a file: {key}")

        if size_bytes is None:
            head = self.s3_client.head_object(Bucket=bucket, Key=key)
            size_bytes = head.get("ContentLength", 0)

        file_size_mb = size_bytes / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum of {settings.MAX_FILE_SIZE_MB}MB",
            )

        doc_type = self._document_type_for_key(key)
        document_id = str(uuid.uuid4())
        s3_path = f"s3://{bucket}/{key}"

        return Document(
            document_id=document_id,
            file_name=file_name,
            document_type=doc_type,
            status=DocumentStatus.INGESTED,
            metadata={
                "bucket": bucket,
                "key": key,
                "size_bytes": size_bytes,
                "etag": record["s3"]["object"].get("eTag"),
                "version_id": record["s3"]["object"].get("versionId"),
                "event_name": record.get("eventName"),
                "event_time": record.get("eventTime"),
            },
            source_s3_path=s3_path,
        )

    def _document_type_for_key(self, key: str) -> DocumentType:
        extension = Path(key).suffix.lstrip(".").lower()
        image_extensions = {"jpg", "jpeg", "png"}

        if extension in image_extensions:
            return DocumentType.IMAGE

        try:
            return DocumentType[extension.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

    def _publish_ingestion_message(self, document: Document, record: Dict[str, Any]) -> None:
        if not settings.AWS_SQS_QUEUE_URL:
            raise HTTPException(status_code=500, detail="AWS_SQS_QUEUE_URL is not configured")

        message = {
            "document_id": document.document_id,
            "s3_path": document.source_s3_path,
            "file_name": document.file_name,
            "document_type": document.document_type,
            "metadata": document.metadata,
            "source_event": {
                "event_name": record.get("eventName"),
                "event_time": record.get("eventTime"),
                "event_source": record.get("eventSource"),
            },
        }

        self.sqs_client.send_message(
            QueueUrl=settings.AWS_SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                "document_type": {
                    "StringValue": document.document_type,
                    "DataType": "String",
                },
                "document_id": {
                    "StringValue": document.document_id,
                    "DataType": "String",
                },
            },
        )


# Initialize service
ingestion_service = DocumentIngestionService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    # Startup
    logger.info("Document Ingestion Service started")
    yield
    # Shutdown
    logger.info("Document Ingestion Service shutdown")


# Create FastAPI app
app = FastAPI(
    title="Document Ingestion Service",
    description="Handles S3 object-created events and ingestion into the RAG system",
    version="1.0.0",
    lifespan=lifespan,
)


# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "document-ingestion",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/ingest")
async def ingest_document(
    event: Dict[str, Any] = Body(...),
):
    """
    Ingest documents from an S3 object-created event.
    
    Args:
        event: AWS S3 event notification payload
    
    Returns:
        Ingestion status and document info
    """
    documents = await ingestion_service.ingest_s3_event(event)
    return {
        "status": "success",
        "documents_ingested": len(documents),
        "documents": [
            {
                "document_id": document.document_id,
                "file_name": document.file_name,
                "document_type": document.document_type,
                "s3_path": document.source_s3_path,
            }
            for document in documents
        ],
    }


@app.post("/s3-events")
async def ingest_s3_events(event: Dict[str, Any] = Body(...)):
    """Alias endpoint for S3 event ingestion."""
    return await ingest_document(event)


@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document status"""
    # TODO: Implement document status retrieval from MongoDB
    return {
        "document_id": document_id,
        "status": "indexed",
    }


if __name__ == "__main__":
    import uvicorn
    
    # Setup observability
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
    )
