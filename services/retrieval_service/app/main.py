"""
Retrieval Service
Handles vector search and document retrieval
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import List, Dict, Optional
from datetime import datetime
import sys
from pathlib import Path
import pinecone
import redis.asyncio as redis
from pymongo import MongoClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings, VectorDBType
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import RetrievedDocument

logger = get_logger(__name__)


class RetrievalService:
    """Service for retrieving documents from vector DB"""
    
    def __init__(self):
        self.vector_db_type = settings.VECTOR_DB_TYPE
        self.pinecone_index = None
        self.redis_client = None
        self.mongo_client = None
    
    async def initialize(self):
        """Initialize vector DB and caching"""
        # Initialize Pinecone
        if self.vector_db_type == VectorDBType.PINECONE:
            pinecone.init(api_key=settings.PINECONE_API_KEY)
            self.pinecone_index = pinecone.Index("rag-documents")
            logger.info("Pinecone initialized")
        
        # Initialize Redis cache
        self.redis_client = await redis.from_url(settings.redis_url, decode_responses=True)
        
        # Initialize MongoDB for metadata
        self.mongo_client = MongoClient(settings.MONGODB_URI)
        self.db = self.mongo_client[settings.MONGODB_DATABASE]
        self.documents_collection = self.db['documents']
    
    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.mongo_client:
            self.mongo_client.close()
    
    async def retrieve(
        self,
        query_embedding: List[float],
        k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[RetrievedDocument]:
        """
        Retrieve documents similar to query embedding
        
        Args:
            query_embedding: Query embedding vector
            k: Number of documents to retrieve
            filters: Optional metadata filters
        
        Returns:
            List of retrieved documents
        """
        try:
            # Query Pinecone
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=k,
                include_metadata=True,
                filter=filters,
            )
            
            retrieved_docs = []
            for match in results.matches:
                # Get document metadata from MongoDB
                doc_id = match.metadata.get("document_id")
                chunk_idx = match.metadata.get("chunk_index")
                
                doc = self.documents_collection.find_one({"document_id": doc_id})
                
                if doc:
                    retrieved_docs.append(RetrievedDocument(
                        document_id=doc_id,
                        file_name=doc.get("file_name", ""),
                        chunk_index=chunk_idx,
                        content=match.metadata.get("text", ""),
                        score=match.score,
                        metadata=doc.get("metadata", {}),
                    ))
            
            logger.info(f"Retrieved {len(retrieved_docs)} documents")
            return retrieved_docs
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def index_document(
        self,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: Dict,
    ) -> bool:
        """
        Index document chunks in vector DB
        
        Args:
            document_id: Document ID
            chunks: Text chunks
            embeddings: Chunk embeddings
            metadata: Document metadata
        
        Returns:
            Success status
        """
        try:
            # Prepare vectors for Pinecone
            vectors_to_upsert = []
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = f"{document_id}_{idx}"
                vectors_to_upsert.append((
                    vector_id,
                    embedding,
                    {
                        "document_id": document_id,
                        "chunk_index": idx,
                        "text": chunk,
                        **metadata,
                    }
                ))
            
            # Upsert to Pinecone
            self.pinecone_index.upsert(vectors=vectors_to_upsert)
            
            logger.info(f"Indexed {len(vectors_to_upsert)} vectors for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing document: {str(e)}")
            return False


retrieval_service = RetrievalService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await retrieval_service.initialize()
    logger.info("Retrieval Service started")
    yield
    await retrieval_service.close()
    logger.info("Retrieval Service shutdown")


app = FastAPI(
    title="Retrieval Service",
    description="Retrieves documents from vector DB",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "retrieval-service",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/retrieve")
async def retrieve_documents(query_embedding: List[float], k: int = 5):
    """Retrieve similar documents"""
    documents = await retrieval_service.retrieve(query_embedding, k)
    return {
        "status": "success",
        "count": len(documents),
        "documents": documents,
    }


@app.post("/index")
async def index_document(
    document_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    metadata: Dict,
):
    """Index document in vector DB"""
    success = await retrieval_service.index_document(document_id, chunks, embeddings, metadata)
    return {
        "status": "success" if success else "failed",
        "document_id": document_id,
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
