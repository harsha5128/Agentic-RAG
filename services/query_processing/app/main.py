"""
Query Processing Service - Production Architecture
Implements complete RAG pipeline with agentic orchestration

Architecture:
├── core/           # Core service logic
├── pipeline/       # RAG pipeline components
├── agents/         # Agent orchestration integration
├── memory/         # Memory management
├── cache/          # Multi-level caching
└── evaluation/     # Self-RAG evaluation
"""

from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import sys
from pathlib import Path
import asyncio
import re
import json
import hashlib

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.base_service import BaseService
from common.config import settings
from common.observability import get_logger
from common.exceptions import QueryProcessingError, ErrorCode
from common.schemas import Query, QueryResult, RetrievedDocument

# Import pipeline components
from .pipeline.query_processor import QueryProcessor
from .pipeline.context_manager import ContextManager
from .pipeline.prompt_builder import PromptBuilder
from .pipeline.response_formatter import ResponseFormatter
from .agents.agent_orchestrator import AgentOrchestrator
from .memory.memory_manager import MemoryManager
from .cache.cache_manager import CacheManager
from .evaluation.self_rag_evaluator import SelfRAGEvaluator

logger = get_logger(__name__)


class QueryProcessingService(BaseService):
    """
    Production-grade Query Processing Service implementing complete RAG pipeline

    Pipeline Flow:
    1. Query Cleaning & Normalization
    2. Query Rewriting (optional)
    3. Embedding (with cache check)
    4. Retrieval (vector DB + hybrid search)
    5. Retrieval Cache (result-level cache)
    6. Self-RAG Retrieval Evaluation
    7. Context Refinement (filter, merge, summarize)
    8. Context Cache (compressed summaries)
    9. Memory Injection (last-k + summary)
    10. OOS Detection / Domain check
    11. Prompt Construction (system + memory + context + instructions)
    12. Prompt Template Cache
    13. LLM Call (with response cache/safeguard)
    14. Self-RAG Generation Evaluation (faithfulness, groundedness)
    15. Response Post-processing & Formatting
    16. Result-level Cache
    17. Telemetry & Return to User
    """

    def __init__(self):
        super().__init__("query-processing-service")
        self.query_processor = None
        self.context_manager = None
        self.prompt_builder = None
        self.response_formatter = None
        self.agent_orchestrator = None
        self.memory_manager = None
        self.cache_manager = None
        self.self_rag_evaluator = None

    async def _initialize_dependencies(self) -> None:
        """Initialize all pipeline components"""
        # Core pipeline components
        self.query_processor = QueryProcessor(self.mongodb_client, self.redis_client)
        self.context_manager = ContextManager(self.redis_client)
        self.prompt_builder = PromptBuilder(self.redis_client)
        self.response_formatter = ResponseFormatter()

        # Agentic components
        self.agent_orchestrator = AgentOrchestrator(
            agent_service_url=settings.AGENT_ORCHESTRATION_URL
        )

        # Memory and caching
        self.memory_manager = MemoryManager(self.mongodb_client, self.redis_client)
        self.cache_manager = CacheManager(self.redis_client)

        # Evaluation
        self.self_rag_evaluator = SelfRAGEvaluator(
            evaluation_service_url=settings.EVALUATION_SERVICE_URL
        )

        # Register health checks
        self.register_dependency("query_processor", lambda: self._check_query_processor())
        self.register_dependency("agent_orchestrator", lambda: self._check_agent_orchestrator())
        self.register_dependency("memory_manager", lambda: self._check_memory_manager())

    async def _check_query_processor(self) -> bool:
        """Check query processor health"""
        try:
            # Simple health check - could be enhanced
            return self.query_processor is not None
        except Exception:
            return False

    async def _check_agent_orchestrator(self) -> bool:
        """Check agent orchestrator connectivity"""
        try:
            # TODO: Implement actual health check
            return True
        except Exception:
            return False

    async def _check_memory_manager(self) -> bool:
        """Check memory manager health"""
        try:
            return self.memory_manager is not None
        except Exception:
            return False

    async def process_query(
        self,
        query: Query,
        use_agentic: bool = True,
        enable_memory: bool = True,
        enable_evaluation: bool = True,
    ) -> QueryResult:
        """
        Execute complete RAG pipeline with agentic orchestration

        Args:
            query: Input query
            use_agentic: Whether to use multi-agent reasoning
            enable_memory: Whether to inject memory context
            enable_evaluation: Whether to perform self-RAG evaluation

        Returns:
            Complete query result with all pipeline outputs
        """
        start_time = datetime.utcnow()

        try:
            logger.info(f"Starting RAG pipeline for query: {query.query_id}")

            # 1. Query Cleaning & Normalization
            cleaned_query = await self.query_processor.clean_and_normalize(query)

            # 2. Query Rewriting (optional)
            rewritten_query = await self.query_processor.rewrite_query(cleaned_query)

            # 3. Embedding (with cache check)
            query_embedding = await self._get_query_embedding(rewritten_query)

            # 4. Retrieval (vector DB + hybrid search)
            retrieved_docs = await self._retrieve_documents(query_embedding, rewritten_query)

            # 5. Retrieval Cache (result-level cache)
            cached_retrieval = await self.cache_manager.get_retrieval_cache(
                rewritten_query.query_id, query_embedding
            )
            if cached_retrieval:
                retrieved_docs = cached_retrieval
            else:
                await self.cache_manager.set_retrieval_cache(
                    rewritten_query.query_id, retrieved_docs
                )

            # 6. Self-RAG Retrieval Evaluation
            if enable_evaluation:
                retrieval_metrics = await self.self_rag_evaluator.evaluate_retrieval(
                    rewritten_query, retrieved_docs
                )

            # 7. Context Refinement (filter, merge, summarize)
            refined_context = await self.context_manager.refine_context(
                retrieved_docs, rewritten_query
            )

            # 8. Context Cache (compressed summaries)
            context_key = f"context:{hash(str(refined_context))}"
            cached_context = await self.cache_manager.get_context_cache(context_key)
            if not cached_context:
                cached_context = await self.context_manager.compress_context(refined_context)
                await self.cache_manager.set_context_cache(context_key, cached_context)

            # 9. Memory Injection (last-k + summary)
            memory_context = ""
            if enable_memory:
                memory_context = await self.memory_manager.get_relevant_memory(
                    rewritten_query, k=settings.MEMORY_LAST_K
                )

            # 10. OOS Detection / Domain check
            oos_detected = await self._detect_out_of_scope(rewritten_query, refined_context)

            # 11. Prompt Construction (system + memory + context + instructions)
            prompt = await self.prompt_builder.build_prompt(
                rewritten_query, cached_context, memory_context, oos_detected
            )

            # 12. Prompt Template Cache
            prompt_key = f"prompt:{hash(prompt.system_prompt + prompt.user_prompt)}"
            cached_prompt = await self.cache_manager.get_prompt_cache(prompt_key)
            if not cached_prompt:
                await self.cache_manager.set_prompt_cache(prompt_key, prompt)

            # Agentic Processing Branch
            if use_agentic and not oos_detected:
                # Use multi-agent orchestration for complex queries
                agent_result = await self.agent_orchestrator.orchestrate_query(
                    rewritten_query, cached_context, memory_context
                )

                # 13. LLM Call (with response cache/safeguard) - handled by agents
                raw_response = agent_result.response
                agent_thoughts = agent_result.thoughts

            else:
                # Standard RAG pipeline
                # 13. LLM Call (with response cache/safeguard)
                raw_response = await self._call_llm_with_cache(prompt)

                # For non-agentic, generate simple thoughts
                agent_thoughts = f"Processed query using standard RAG pipeline. OOS: {oos_detected}"

            # 14. Self-RAG Generation Evaluation (faithfulness, groundedness)
            if enable_evaluation:
                generation_metrics = await self.self_rag_evaluator.evaluate_generation(
                    rewritten_query, raw_response, cached_context
                )

            # 15. Response Post-processing & Formatting
            formatted_response = await self.response_formatter.format_response(
                raw_response, rewritten_query, retrieved_docs
            )

            # 16. Result-level Cache
            result_key = f"result:{query.query_id}"
            await self.cache_manager.set_result_cache(result_key, formatted_response)

            # 17. Telemetry, Logging, Observability
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update memory with this interaction
            if enable_memory:
                await self.memory_manager.add_interaction(
                    rewritten_query, formatted_response, retrieved_docs
                )

            # Create final result
            result = QueryResult(
                query_id=query.query_id,
                answer=formatted_response.final_answer,
                retrieved_documents=retrieved_docs,
                agent_thoughts=agent_thoughts,
                confidence_score=formatted_response.confidence_score,
                token_usage=formatted_response.token_usage,
                processing_time_ms=processing_time,
                metadata={
                    "pipeline_steps": [
                        "query_cleaning", "query_rewriting", "embedding",
                        "retrieval", "retrieval_cache", "retrieval_evaluation",
                        "context_refinement", "context_cache", "memory_injection",
                        "oos_detection", "prompt_construction", "prompt_cache",
                        "llm_call", "generation_evaluation", "response_formatting",
                        "result_cache"
                    ],
                    "oos_detected": oos_detected,
                    "agentic_used": use_agentic and not oos_detected,
                    "evaluation_enabled": enable_evaluation,
                    "memory_enabled": enable_memory,
                }
            )

            logger.info(f"Completed RAG pipeline for query: {query.query_id} in {processing_time}ms")
            return result

        except Exception as e:
            logger.error(f"RAG pipeline failed for query {query.query_id}: {str(e)}")
            raise QueryProcessingError(
                ErrorCode.QUERY_PROCESSING_FAILED,
                f"Query processing failed: {str(e)}",
                {"query_id": query.query_id, "stage": "pipeline_execution"},
                e
            )

    async def _get_query_embedding(self, query: Query) -> List[float]:
        """Get query embedding with caching"""
        return await self.cache_manager.get_embedding_cache(
            f"query_embedding:{query.query_id}",
            lambda: self._generate_embedding(query.query_text)
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text via embedding service"""
        try:
            import aiohttp
            import json

            async with aiohttp.ClientSession() as session:
                payload = {"text": text}
                async with session.post(
                    f"{settings.EMBEDDING_SERVICE_URL}/embed",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Embedding service error: {response.status}")

                    result = await response.json()
                    return result["embedding"]

        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            # Fallback: return zero vector (not ideal but prevents crash)
            return [0.0] * settings.VECTOR_DB_DIMENSION

    async def _retrieve_documents(
        self,
        query_embedding: List[float],
        query: Query
    ) -> List[RetrievedDocument]:
        """Retrieve documents using retrieval service"""
        try:
            import aiohttp
            import json

            async with aiohttp.ClientSession() as session:
                payload = {
                    "query_embedding": query_embedding,
                    "query_text": query.query_text,
                    "k": settings.RETRIEVAL_K,
                    "filters": query.filters
                }

                async with session.post(
                    f"{settings.RETRIEVAL_SERVICE_URL}/retrieve",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Retrieval service error: {response.status}")

                    result = await response.json()
                    return [RetrievedDocument(**doc) for doc in result["documents"]]

        except Exception as e:
            logger.error(f"Document retrieval failed: {str(e)}")
            # Fallback: return empty list
            return []

    async def _detect_out_of_scope(self, query: Query, context: str) -> bool:
        """Detect if query is out of scope/domain"""
        # Simple heuristic - can be enhanced with ML
        oos_keywords = ["weather", "sports", "politics", "current events", "news", "celebrity"]
        query_lower = query.query_text.lower()

        for keyword in oos_keywords:
            if keyword in query_lower:
                return True

        # Check if we have relevant context
        if not context or len(context.strip()) < 50:
            return True

        return False

    async def _call_llm_with_cache(self, prompt) -> str:
        """Call LLM with response caching and safeguards"""
        try:
            import aiohttp
            import json

            # Create cache key from prompt hash
            prompt_hash = hashlib.md5(
                (prompt.system_prompt + prompt.user_prompt).encode()
            ).hexdigest()

            # Check cache first
            cached_response = await self.cache_manager.get_result_cache(f"llm:{prompt_hash}")
            if cached_response:
                logger.debug("LLM response cache hit")
                return cached_response.get("response", "")

            # Call LLM service (assuming we have a separate LLM service, or use OpenAI directly)
            # For now, using OpenAI directly as fallback
            import openai

            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            response = client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": prompt.system_prompt},
                    {"role": "user", "content": prompt.user_prompt}
                ],
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                top_p=settings.TOP_P,
            )

            generated_text = response.choices[0].message.content

            # Cache the response
            await self.cache_manager.set_result_cache(f"llm:{prompt_hash}", {
                "response": generated_text,
                "model": settings.LLM_MODEL_NAME,
                "timestamp": datetime.utcnow().isoformat()
            })

            return generated_text

        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            # Fallback response
            return "I apologize, but I'm currently unable to generate a response. Please try again later."


# Global service instance
query_service = QueryProcessingService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle"""
    await query_service.initialize()
    logger.info("Query Processing Service started")
    yield
    await query_service.close()
    logger.info("Query Processing Service shutdown")


app = FastAPI(
    title="Query Processing Service",
    description="Complete RAG pipeline with agentic orchestration",
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/process")
async def process_query(
    query: Query,
    use_agentic: bool = True,
    enable_memory: bool = True,
    enable_evaluation: bool = True,
):
    """
    Process query through complete RAG pipeline

    - **use_agentic**: Enable multi-agent reasoning for complex queries
    - **enable_memory**: Inject conversation memory
    - **enable_evaluation**: Perform self-RAG evaluation
    """
    try:
        result = await query_service.process_query(
            query, use_agentic, enable_memory, enable_evaluation
        )
        return {
            "status": "success",
            "query_id": result.query_id,
            "answer": result.answer,
            "confidence_score": result.confidence_score,
            "processing_time_ms": result.processing_time_ms,
            "metadata": result.metadata,
        }
    except QueryProcessingError as e:
        logger.error(f"Query processing failed: {str(e)}")
        raise HTTPException(status_code=422, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": "Internal server error"})


@app.get("/health")
async def health_check():
    """Health check"""
    return await query_service.check_health()


@app.get("/ready")
async def readiness():
    """Readiness probe"""
    return await query_service.readiness_probe()


@app.get("/live")
async def liveness():
    """Liveness probe"""
    return await query_service.liveness_probe()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
