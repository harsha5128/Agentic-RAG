"""
Context Manager - Handles context refinement, compression, and caching
"""

import json
import re
from typing import List, Dict, Any
import redis.asyncio as redis

from common.config import settings
from common.observability import get_logger
from common.schemas import Query, RetrievedDocument

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    BM25Okapi = None

logger = get_logger(__name__)


class ContextManager:
    """Manages context processing and optimization"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def refine_context(
        self,
        retrieved_docs: List[RetrievedDocument],
        query: Query
    ) -> Dict[str, Any]:
        """
        Refine and filter retrieved context

        - Remove irrelevant documents
        - Merge overlapping content
        - Prioritize high-scoring documents
        - Limit context length
        """
        try:
            if not retrieved_docs:
                return {"context": "", "sources": [], "refined": False}

            # First-pass vector score ordering from retrieval service.
            sorted_docs = sorted(retrieved_docs, key=lambda x: x.score, reverse=True)

            # Filter low-scoring documents
            min_score = 0.1  # Configurable threshold
            filtered_docs = [doc for doc in sorted_docs if doc.score >= min_score]

            # Production path: combine vector score with BM25 lexical relevance.
            # Custom score-only sorting is kept as fallback when rank_bm25 is absent.
            reranked_docs = self._hybrid_rerank(filtered_docs, query)

            # Select diverse chunks so one document does not crowd out all context.
            max_docs = min(settings.RETRIEVAL_K, len(reranked_docs))
            top_docs = self._select_diverse_chunks(reranked_docs, max_docs)

            # Build context string
            context_parts = []
            sources = []

            for i, doc in enumerate(top_docs):
                # Add document header
                header = f"Document {i+1} (Score: {doc.score:.3f}, Source: {doc.file_name}):"
                context_parts.append(header)

                # Add content
                context_parts.append(doc.content)

                # Track source
                sources.append({
                    "document_id": doc.document_id,
                    "file_name": doc.file_name,
                    "chunk_index": doc.chunk_index,
                    "score": doc.score,
                    "content_length": len(doc.content)
                })

            context = "\n\n".join(context_parts)

            # Limit total context length
            max_context_length = 8000  # Configurable
            if len(context) > max_context_length:
                context = context[:max_context_length] + "...[truncated]"
                logger.debug(f"Truncated context to {max_context_length} characters")

            refined_context = {
                "context": context,
                "sources": sources,
                "total_docs": len(retrieved_docs),
                "filtered_docs": len(filtered_docs),
                "selected_docs": len(top_docs),
                "context_length": len(context),
                "refined": True,
                "refinement_strategy": "hybrid_bm25_vector_diverse",
            }

            logger.debug(f"Refined context: {len(retrieved_docs)} -> {len(top_docs)} docs, {len(context)} chars")
            return refined_context

        except Exception as e:
            logger.error(f"Context refinement failed: {str(e)}")
            # Return basic context as fallback
            basic_context = "\n\n".join([doc.content for doc in retrieved_docs[:5]])
            return {
                "context": basic_context,
                "sources": [{"document_id": doc.document_id, "score": doc.score} for doc in retrieved_docs[:5]],
                "refined": False,
                "error": str(e)
            }

    async def compress_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress context for better caching and processing

        - Extract key information
        - Summarize if too long
        - Create compressed representation
        """
        try:
            # For now, return as-is (can be enhanced with summarization)
            compressed = {
                **context,
                "compressed": True,
                "compression_ratio": 1.0,  # No compression yet
            }

            return compressed

        except Exception as e:
            logger.error(f"Context compression failed: {str(e)}")
            return context

    def _hybrid_rerank(
        self,
        docs: List[RetrievedDocument],
        query: Query,
        vector_weight: float = 0.65,
    ) -> List[RetrievedDocument]:
        if not docs or not BM25Okapi:
            return docs

        try:
            tokenized_docs = [self._tokenize(doc.content) for doc in docs]
            bm25 = BM25Okapi(tokenized_docs)
            bm25_scores = bm25.get_scores(self._tokenize(query.query_text))
            max_bm25 = max(bm25_scores) if len(bm25_scores) else 0
            max_vector = max(doc.score for doc in docs) or 1.0

            scored = []
            for doc, bm25_score in zip(docs, bm25_scores):
                normalized_bm25 = bm25_score / max_bm25 if max_bm25 else 0.0
                normalized_vector = doc.score / max_vector if max_vector else 0.0
                hybrid_score = (vector_weight * normalized_vector) + (
                    (1 - vector_weight) * normalized_bm25
                )
                scored.append((hybrid_score, doc))

            return [doc for _, doc in sorted(scored, key=lambda item: item[0], reverse=True)]
        except Exception as e:
            logger.warning(f"BM25 hybrid rerank failed, using vector order: {str(e)}")
            return docs

    def _select_diverse_chunks(
        self,
        docs: List[RetrievedDocument],
        max_docs: int,
    ) -> List[RetrievedDocument]:
        selected = []
        per_document_counts = {}

        for doc in docs:
            count = per_document_counts.get(doc.document_id, 0)
            if count >= 2 and len(selected) < max_docs - 1:
                continue
            selected.append(doc)
            per_document_counts[doc.document_id] = count + 1
            if len(selected) >= max_docs:
                break

        return selected

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
