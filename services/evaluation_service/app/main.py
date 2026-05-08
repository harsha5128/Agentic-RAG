"""
Evaluation Service
Evaluates query results and provides metrics
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import Dict, List
from datetime import datetime
import sys
from pathlib import Path
from pymongo import MongoClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import QueryEvaluation, EvaluationMetric

logger = get_logger(__name__)


class EvaluationService:
    """Service for evaluating query results"""
    
    def __init__(self):
        self.mongo_client = None
    
    async def initialize(self):
        """Initialize service"""
        self.mongo_client = MongoClient(settings.MONGODB_URI)
        self.db = self.mongo_client[settings.MONGODB_DATABASE]
        self.evaluations_collection = self.db['evaluations']
        logger.info("Evaluation Service initialized")
    
    async def close(self):
        """Close connections"""
        if self.mongo_client:
            self.mongo_client.close()
    
    async def evaluate_query(
        self,
        query_id: str,
        retrieved_count: int,
        answer_length: int,
        user_feedback: str = None,
        user_rating: int = None,
    ) -> QueryEvaluation:
        """
        Evaluate query result
        
        Args:
            query_id: Query ID
            retrieved_count: Number of documents retrieved
            answer_length: Length of answer
            user_feedback: Optional user feedback
            user_rating: Optional user rating (1-5)
        
        Returns:
            Evaluation results
        """
        metrics = [
            EvaluationMetric(
                metric_name="retrieval_count",
                score=float(min(retrieved_count / 5, 1.0)),
                details={"count": retrieved_count},
            ),
            EvaluationMetric(
                metric_name="answer_completeness",
                score=float(min(answer_length / 500, 1.0)),
                details={"length": answer_length},
            ),
        ]
        
        evaluation = QueryEvaluation(
            query_id=query_id,
            metrics=metrics,
            feedback=user_feedback,
            rating=user_rating,
        )
        
        # Save evaluation
        self.evaluations_collection.insert_one({
            "query_id": query_id,
            "metrics": [m.dict() for m in metrics],
            "feedback": user_feedback,
            "rating": user_rating,
            "created_at": datetime.utcnow(),
        })
        
        logger.info(f"Evaluated query {query_id}")
        return evaluation


evaluation_service = EvaluationService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await evaluation_service.initialize()
    logger.info("Evaluation Service started")
    yield
    await evaluation_service.close()
    logger.info("Evaluation Service shutdown")


app = FastAPI(
    title="Evaluation Service",
    description="Evaluates query results and provides metrics",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "evaluation-service",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/evaluate")
async def evaluate_query(
    query_id: str,
    retrieved_count: int,
    answer_length: int,
    user_feedback: str = None,
    user_rating: int = None,
):
    """Evaluate query result"""
    evaluation = await evaluation_service.evaluate_query(
        query_id,
        retrieved_count,
        answer_length,
        user_feedback,
        user_rating,
    )
    return {
        "status": "success",
        "query_id": evaluation.query_id,
        "metrics": evaluation.metrics,
    }


@app.get("/metrics/{query_id}")
async def get_metrics(query_id: str):
    """Get evaluation metrics for a query"""
    # TODO: Retrieve from MongoDB
    return {
        "query_id": query_id,
        "metrics": [],
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
