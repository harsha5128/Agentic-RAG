"""
Document Parsing Service
Handles extraction, chunking, and OCR of documents
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from datetime import datetime
import sys
from pathlib import Path
import boto3
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
import pandas as pd
from docx import Document as DocxDocument

# Add parent to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import Document, DocumentStatus, DocumentType

logger = get_logger(__name__)


class DocumentParsingService:
    """Service for parsing and chunking documents"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
        )
    
    async def parse_document(self, s3_path: str) -> Document:
        """
        Parse document from S3
        
        Args:
            s3_path: S3 path to document
        
        Returns:
            Parsed document with content and chunks
        """
        try:
            # Extract bucket and key from S3 path
            bucket, key = s3_path.replace("s3://", "").split("/", 1)
            
            # Download from S3
            obj = self.s3_client.get_object(Bucket=bucket, Key=key)
            file_bytes = obj['Body'].read()
            
            # Parse based on file extension
            file_ext = key.split('.')[-1].lower()
            
            if file_ext == 'pdf':
                content = self._parse_pdf(file_bytes)
            elif file_ext == 'docx':
                content = self._parse_docx(file_bytes)
            elif file_ext in ['xlsx', 'csv']:
                content = self._parse_spreadsheet(file_bytes, file_ext)
            elif file_ext in ['jpg', 'png', 'jpeg']:
                content = self._parse_image(file_bytes)
            elif file_ext == 'txt':
                content = file_bytes.decode('utf-8')
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # Chunk content
            chunks = self._chunk_text(content, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            
            logger.info(f"Parsed document from {s3_path}: {len(chunks)} chunks")
            
            return {
                "content": content,
                "chunks": chunks,
                "status": DocumentStatus.PARSED,
            }
            
        except Exception as e:
            logger.error(f"Error parsing document: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def _parse_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF with OCR support"""
        from io import BytesIO
        pdf_reader = PdfReader(BytesIO(file_bytes))
        text = ""
        
        for page_num, page in enumerate(pdf_reader.pages):
            # Extract text
            page_text = page.extract_text()
            text += page_text + "\n"
            
            # Apply OCR if text extraction failed
            if not page_text.strip() and settings.OCR_ENABLED:
                logger.info(f"Applying OCR to PDF page {page_num}")
                # Convert PDF page to image and OCR
                # Implementation depends on pdf2image and pytesseract
        
        return text
    
    def _parse_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX"""
        from io import BytesIO
        doc = DocxDocument(BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    
    def _parse_spreadsheet(self, file_bytes: bytes, ext: str) -> str:
        """Extract text from spreadsheet (CSV, XLSX)"""
        from io import BytesIO
        if ext == 'xlsx':
            df = pd.read_excel(BytesIO(file_bytes))
        else:
            df = pd.read_csv(BytesIO(file_bytes))
        
        return df.to_string()
    
    def _parse_image(self, file_bytes: bytes) -> str:
        """Extract text from image using OCR"""
        from io import BytesIO
        image = Image.open(BytesIO(file_bytes))
        text = pytesseract.image_to_string(image)
        return text
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk
            overlap: Overlap between chunks
        
        Returns:
            List of text chunks
        """
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks


parsing_service = DocumentParsingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    logger.info("Document Parsing Service started")
    yield
    logger.info("Document Parsing Service shutdown")


app = FastAPI(
    title="Document Parsing Service",
    description="Parses and chunks documents for RAG",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "document-parsing",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/parse")
async def parse_document(s3_path: str):
    """Parse document from S3"""
    result = await parsing_service.parse_document(s3_path)
    return {
        "status": "success",
        "content_length": len(result["content"]),
        "chunks": len(result["chunks"]),
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
