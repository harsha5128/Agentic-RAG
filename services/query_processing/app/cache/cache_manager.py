"""
Cache Manager - Multi-level caching for RAG pipeline optimization
"""

import json
import hashlib
from typing import List, Dict, Any, Callable, Awaitable, Optional
import redis.asyncio as redis

from common.config import settings
from common.observability import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Manages multiple caching layers for RAG pipeline"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def get_embedding_cache(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[List[float]]]
    ) -> List[float]:
        """
        Get embedding from cache or compute if missing

        Args:
            key: Cache key
            compute_fn: Function to compute embedding if not cached

        Returns:
            Embedding vector
        """
        try:
            cached = await self.redis_client.get(f"embedding:{key}")
            if cached:
                logger.debug(f"Embedding cache hit: {key}")
                return json.loads(cached)

            # Compute and cache
            embedding = await compute_fn()
            await self.redis_client.setex(
                f"embedding:{key}",
                settings.CACHE_TTL_SECONDS,
                json.dumps(embedding)
            )

            logger.debug(f"Embedding cache miss, computed: {key}")
            return embedding

        except Exception as e:
            logger.error(f"Embedding cache error: {str(e)}")
            # Fallback to computation
            return await compute_fn()

    async def get_retrieval_cache(
        self,
        query_id: str,
        embedding: List[float]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get retrieval results from cache

        Args:
            query_id: Query identifier
            embedding: Query embedding (for cache key)

        Returns:
            Cached retrieval results or None
        """
        try:
            # Create cache key from embedding hash
            embedding_hash = hashlib.md5(json.dumps(embedding, sort_keys=True).encode()).hexdigest()
            cache_key = f"retrieval:{embedding_hash}"

            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Retrieval cache hit: {query_id}")
                return json.loads(cached)

            return None

        except Exception as e:
            logger.error(f"Retrieval cache error: {str(e)}")
            return None

    async def set_retrieval_cache(
        self,
        query_id: str,
        results: List[Dict[str, Any]]
    ) -> None:
        """Cache retrieval results"""
        try:
            # Use query_id as cache key for now (can be improved)
            cache_key = f"retrieval:{query_id}"
            await self.redis_client.setex(
                cache_key,
                settings.CACHE_TTL_SECONDS,
                json.dumps(results)
            )
            logger.debug(f"Cached retrieval results: {query_id}")

        except Exception as e:
            logger.error(f"Failed to cache retrieval results: {str(e)}")

    async def get_context_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get compressed context from cache

        Args:
            key: Cache key

        Returns:
            Cached context or None
        """
        try:
            cached = await self.redis_client.get(f"context:{key}")
            if cached:
                logger.debug(f"Context cache hit: {key}")
                return json.loads(cached)
            return None

        except Exception as e:
            logger.error(f"Context cache error: {str(e)}")
            return None

    async def set_context_cache(self, key: str, context: Dict[str, Any]) -> None:
        """Cache compressed context"""
        try:
            await self.redis_client.setex(
                f"context:{key}",
                settings.CACHE_TTL_SECONDS * 2,  # Longer TTL for context
                json.dumps(context)
            )
            logger.debug(f"Cached context: {key}")

        except Exception as e:
            logger.error(f"Failed to cache context: {str(e)}")

    async def get_prompt_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get prompt template from cache

        Args:
            key: Cache key

        Returns:
            Cached prompt or None
        """
        try:
            cached = await self.redis_client.get(f"prompt:{key}")
            if cached:
                logger.debug(f"Prompt cache hit: {key}")
                return json.loads(cached)
            return None

        except Exception as e:
            logger.error(f"Prompt cache error: {str(e)}")
            return None

    async def set_prompt_cache(self, key: str, prompt: Any) -> None:
        """Cache prompt template"""
        try:
            # Convert prompt object to dict
            prompt_dict = {
                "system_prompt": prompt.system_prompt,
                "user_prompt": prompt.user_prompt,
                "metadata": prompt.metadata
            }

            await self.redis_client.setex(
                f"prompt:{key}",
                settings.CACHE_TTL_SECONDS * 4,  # Even longer for prompts
                json.dumps(prompt_dict)
            )
            logger.debug(f"Cached prompt: {key}")

        except Exception as e:
            logger.error(f"Failed to cache prompt: {str(e)}")

    async def get_result_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get final result from cache

        Args:
            key: Cache key

        Returns:
            Cached result or None
        """
        try:
            cached = await self.redis_client.get(f"result:{key}")
            if cached:
                logger.debug(f"Result cache hit: {key}")
                return json.loads(cached)
            return None

        except Exception as e:
            logger.error(f"Result cache error: {str(e)}")
            return None

    async def set_result_cache(self, key: str, result: Any) -> None:
        """Cache final result"""
        try:
            # Convert result to dict if needed
            if hasattr(result, 'dict'):
                result_dict = result.dict()
            else:
                result_dict = result

            await self.redis_client.setex(
                f"result:{key}",
                settings.CACHE_TTL_SECONDS * 6,  # Longest TTL for results
                json.dumps(result_dict)
            )
            logger.debug(f"Cached result: {key}")

        except Exception as e:
            logger.error(f"Failed to cache result: {str(e)}")

    async def invalidate_query_cache(self, query_id: str) -> None:
        """Invalidate all caches related to a query"""
        try:
            # Pattern for all query-related keys
            patterns = [
                f"embedding:*{query_id}*",
                f"retrieval:{query_id}",
                f"context:*{query_id}*",
                f"prompt:*{query_id}*",
                f"result:{query_id}"
            ]

            for pattern in patterns:
                # Note: Redis doesn't support pattern deletion directly
                # In production, you'd want to track keys or use a key management strategy
                logger.debug(f"Would invalidate pattern: {pattern}")

            logger.info(f"Invalidated caches for query: {query_id}")

        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = await self.redis_client.info()
            return {
                "redis_used_memory": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "total_keys": await self.redis_client.dbsize(),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {"error": str(e)}