"""
Embedding Service
Generates embeddings for document chunks using OpenAI
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import List
from datetime import datetime
import sys
from pathlib import Path
from openai import OpenAI
import redis.asyncio as redis
import json
from tenacity import retry, wait_exponential, stop_after_attempt

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating embeddings"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.redis_client = None
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(settings.redis_url, decode_responses=True)
        logger.info("Embedding Service initialized")
    
    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()
    
    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        try:
            # Check cache
            cache_key = f"embedding:{hash(text)}"
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                logger.debug(f"Cache hit for embedding")
                return json.loads(cached)
            
            # Generate embedding
            response = self.client.embeddings.create(
                model=settings.EMBEDDING_MODEL_NAME,
                input=text,
            )
            
            embedding = response.data[0].embedding
            
            # Cache result
            await self.redis_client.setex(
                cache_key,
                settings.CACHE_TTL_SECONDS,
                json.dumps(embedding)
            )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts
        
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings


embedding_service = EmbeddingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await embedding_service.initialize()
    logger.info("Embedding Service started")
    yield
    await embedding_service.close()
    logger.info("Embedding Service shutdown")


app = FastAPI(
    title="Embedding Service",
    description="Generates embeddings for RAG system",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "embedding-service",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/embed")
async def embed_text(text: str):
    """
    Generate embedding for text
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding vector
    """
    embedding = await embedding_service.generate_embedding(text)
    return {
        "status": "success",
        "embedding": embedding,
        "dimension": len(embedding),
    }


@app.post("/embed-batch")
async def embed_batch(texts: List[str]):
    """Generate embeddings for multiple texts"""
    embeddings = await embedding_service.generate_batch_embeddings(texts)
    return {
        "status": "success",
        "count": len(embeddings),
        "dimension": len(embeddings[0]) if embeddings else 0,
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
