"""
Query Processing Service
Handles query routing and LLM response generation
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime
import sys
from pathlib import Path
from openai import OpenAI
import redis.asyncio as redis

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import Query, QueryResult

logger = get_logger(__name__)


class QueryProcessingService:
    """Service for processing queries and generating responses"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.redis_client = None
    
    async def initialize(self):
        """Initialize service"""
        self.redis_client = await redis.from_url(settings.redis_url, decode_responses=True)
        logger.info("Query Processing Service initialized")
    
    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def process_query(
        self,
        query: Query,
        retrieved_contexts: List[str],
    ) -> QueryResult:
        """
        Process query and generate response
        
        Args:
            query: Query object
            retrieved_contexts: Retrieved document contexts
        
        Returns:
            Query result with generated answer
        """
        try:
            # Build context
            context = "\n\n".join([f"Document {i+1}:\n{ctx}" for i, ctx in enumerate(retrieved_contexts)])
            
            # Build prompt
            system_prompt = """You are a helpful assistant that answers questions based on provided documents.
            
Provide accurate, concise answers based ONLY on the provided context.
If the answer cannot be found in the context, say so clearly.
Format your response clearly with proper structure."""
            
            user_prompt = f"""Based on the following documents, answer the question:

Question: {query.query_text}

Documents:
{context}

Answer:"""
            
            # Track token usage
            prompt_tokens = len(user_prompt.split())
            
            # Generate response
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                top_p=settings.TOP_P,
            )
            
            answer = response.choices[0].message.content
            completion_tokens = len(answer.split())
            
            # Create result
            result = QueryResult(
                query_id=query.query_id,
                answer=answer,
                agent_thoughts=None,
                confidence_score=0.8,
                token_usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )
            
            logger.info(f"Processed query {query.query_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


query_service = QueryProcessingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await query_service.initialize()
    logger.info("Query Processing Service started")
    yield
    await query_service.close()
    logger.info("Query Processing Service shutdown")


app = FastAPI(
    title="Query Processing Service",
    description="Processes queries and generates responses",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "query-processing",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/process")
async def process_query(query: Query, contexts: List[str]):
    """Process query and generate response"""
    result = await query_service.process_query(query, contexts)
    return {
        "status": "success",
        "query_id": result.query_id,
        "answer": result.answer,
        "token_usage": result.token_usage,
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
