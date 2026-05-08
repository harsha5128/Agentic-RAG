"""
Document Ingestion Service
Handles document uploads via SQS and S3
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uuid
import boto3
from datetime import datetime
from typing import Optional
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
    """Service for managing document ingestion"""
    
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
    
    async def ingest_document(
        self,
        file: UploadFile,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Document:
        """
        Ingest a document by uploading to S3 and publishing to SQS
        
        Args:
            file: Uploaded file
            user_id: Optional user ID
            metadata: Optional metadata dict
        
        Returns:
            Document object with ingestion details
        """
        try:
            # Validate file size
            file.file.seek(0, 2)  # Seek to end
            file_size_mb = file.file.tell() / (1024 * 1024)
            file.file.seek(0)  # Reset to start
            
            if file_size_mb > settings.MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size exceeds maximum of {settings.MAX_FILE_SIZE_MB}MB"
                )
            
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Determine document type
            file_extension = file.filename.split('.')[-1].lower()
            try:
                doc_type = DocumentType[file_extension.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file_extension}"
                )
            
            # Upload to S3
            s3_key = f"documents/{document_id}/{file.filename}"
            self.s3_client.upload_fileobj(
                file.file,
                settings.S3_BUCKET_NAME,
                s3_key,
            )
            s3_path = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
            
            # Create document record
            document = Document(
                document_id=document_id,
                file_name=file.filename,
                document_type=doc_type,
                status=DocumentStatus.INGESTED,
                metadata=metadata or {},
                source_s3_path=s3_path,
            )
            
            # Publish to SQS for parsing
            message = {
                "document_id": document_id,
                "s3_path": s3_path,
                "file_name": file.filename,
                "document_type": doc_type.value,
                "user_id": user_id,
                "metadata": document.metadata,
            }
            
            self.sqs_client.send_message(
                QueueUrl=settings.AWS_SQS_QUEUE_URL,
                MessageBody=str(message),
                MessageAttributes={
                    "document_type": {
                        "StringValue": doc_type.value,
                        "DataType": "String"
                    },
                    "document_id": {
                        "StringValue": document_id,
                        "DataType": "String"
                    }
                }
            )
            
            logger.info(f"Document ingested: {document_id} ({file.filename})")
            return document
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error ingesting document: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


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
    description="Handles document uploads and ingestion into the RAG system",
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
    file: UploadFile = File(...),
    user_id: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Ingest a document
    
    Args:
        file: Document file to ingest
        user_id: Optional user ID
    
    Returns:
        Ingestion status and document info
    """
    document = await ingestion_service.ingest_document(file, user_id)
    return {
        "status": "success",
        "document_id": document.document_id,
        "file_name": document.file_name,
        "document_type": document.document_type.value,
        "s3_path": document.source_s3_path,
    }


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
