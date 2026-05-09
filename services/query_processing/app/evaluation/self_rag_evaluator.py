"""
Self-RAG Evaluator - Evaluates retrieval and generation quality
"""

import aiohttp
import json
from typing import List, Dict, Any
from dataclasses import dataclass

from common.config import settings
from common.observability import get_logger
from common.schemas import Query

logger = get_logger(__name__)


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for self-RAG"""
    faithfulness: float
    groundedness: float
    relevance: float
    completeness: float
    overall_score: float


class SelfRAGEvaluator:
    """Evaluates RAG pipeline components using self-RAG methodology"""

    def __init__(self, evaluation_service_url: str):
        self.evaluation_service_url = evaluation_service_url.rstrip('/')
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def evaluate_retrieval(
        self,
        query: Query,
        retrieved_docs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate retrieval quality

        Args:
            query: The original query
            retrieved_docs: Retrieved documents with scores

        Returns:
            Retrieval evaluation metrics
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Prepare evaluation payload
            payload = {
                "evaluation_type": "retrieval",
                "query": query.dict(),
                "retrieved_documents": retrieved_docs,
                "metrics": ["relevance", "diversity", "coverage"]
            }

            # Call evaluation service
            async with self.session.post(
                f"{self.evaluation_service_url}/evaluate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status != 200:
                    logger.warning(f"Retrieval evaluation failed: {response.status}")
                    return self._default_retrieval_metrics(retrieved_docs)

                result = await response.json()

                logger.debug(f"Retrieval evaluation completed: {result.get('overall_score', 'unknown')}")
                return result

        except Exception as e:
            logger.error(f"Retrieval evaluation error: {str(e)}")
            return self._default_retrieval_metrics(retrieved_docs)

    async def evaluate_generation(
        self,
        query: Query,
        response: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate generation quality using self-RAG metrics

        Args:
            query: The original query
            response: Generated response
            context: Context used for generation

        Returns:
            Generation evaluation metrics
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Prepare evaluation payload
            payload = {
                "evaluation_type": "generation",
                "query": query.dict(),
                "response": response,
                "context": context,
                "metrics": ["faithfulness", "groundedness", "relevance", "completeness"]
            }

            # Call evaluation service
            async with self.session.post(
                f"{self.evaluation_service_url}/evaluate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status != 200:
                    logger.warning(f"Generation evaluation failed: {response.status}")
                    return self._default_generation_metrics(response)

                result = await response.json()

                logger.debug(f"Generation evaluation completed: faithfulness={result.get('faithfulness', 'unknown')}")
                return result

        except Exception as e:
            logger.error(f"Generation evaluation error: {str(e)}")
            return self._default_generation_metrics(response)

    def _default_retrieval_metrics(self, retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Default retrieval metrics when evaluation service is unavailable"""
        try:
            # Simple heuristic-based metrics
            avg_score = sum(doc.get("score", 0) for doc in retrieved_docs) / len(retrieved_docs) if retrieved_docs else 0

            return {
                "relevance": min(avg_score * 2, 1.0),  # Scale up average score
                "diversity": min(len(retrieved_docs) / 5, 1.0),  # More docs = more diverse
                "coverage": min(len(retrieved_docs) / 3, 1.0),  # Coverage based on count
                "overall_score": avg_score,
                "method": "heuristic_fallback"
            }

        except Exception as e:
            logger.error(f"Default retrieval metrics failed: {str(e)}")
            return {
                "relevance": 0.5,
                "diversity": 0.5,
                "coverage": 0.5,
                "overall_score": 0.5,
                "method": "error_fallback"
            }

    def _default_generation_metrics(self, response: str) -> Dict[str, Any]:
        """Default generation metrics when evaluation service is unavailable"""
        try:
            # Simple heuristic-based metrics
            response_length = len(response.split())

            # Faithfulness: assume higher for longer, more detailed responses
            faithfulness = min(response_length / 100, 1.0)

            # Groundedness: check for citations or references
            groundedness = 0.8 if any(word in response.lower() for word in ["according", "based on", "source", "document"]) else 0.5

            # Relevance: assume good unless very short
            relevance = 0.9 if response_length > 20 else 0.6

            # Completeness: based on response structure
            completeness = 0.8 if len(response.split('.')) > 3 else 0.5

            overall_score = (faithfulness + groundedness + relevance + completeness) / 4

            return {
                "faithfulness": faithfulness,
                "groundedness": groundedness,
                "relevance": relevance,
                "completeness": completeness,
                "overall_score": overall_score,
                "method": "heuristic_fallback"
            }

        except Exception as e:
            logger.error(f"Default generation metrics failed: {str(e)}")
            return {
                "faithfulness": 0.5,
                "groundedness": 0.5,
                "relevance": 0.5,
                "completeness": 0.5,
                "overall_score": 0.5,
                "method": "error_fallback"
            }