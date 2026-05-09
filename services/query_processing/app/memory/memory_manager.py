"""
Memory Manager - Handles conversation memory and context injection
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis

from common.config import settings
from common.observability import get_logger
from common.schemas import Query

logger = get_logger(__name__)


class MemoryManager:
    """Manages conversation memory for context injection"""

    def __init__(self, mongo_client: AsyncIOMotorClient, redis_client: redis.Redis):
        self.mongo_client = mongo_client
        self.redis_client = redis_client
        self.db = mongo_client[settings.MONGODB_DATABASE]
        self.memory_collection = self.db.memory

    async def add_interaction(
        self,
        query: Query,
        response: str,
        retrieved_docs: List[Dict[str, Any]]
    ) -> None:
        """
        Add interaction to memory

        Args:
            query: The original query
            response: The generated response
            retrieved_docs: Documents that were retrieved
        """
        try:
            response_text = response if isinstance(response, str) else getattr(response, "final_answer", str(response))
            memory_entry = {
                "session_id": query.session_id,
                "user_id": query.user_id,
                "query_id": query.query_id,
                "query_text": query.query_text,
                "response": response_text,
                "retrieved_docs": [
                    {
                        "document_id": doc.document_id,
                        "file_name": doc.file_name,
                        "score": doc.score
                    } for doc in retrieved_docs[:3]  # Top 3 docs
                ],
                "timestamp": datetime.utcnow(),
                "ttl": datetime.utcnow() + timedelta(days=7)  # 7 day memory
            }

            await self.memory_collection.insert_one(memory_entry)

            # Cache in Redis for fast access
            cache_key = f"memory:{query.session_id}:recent"
            await self.redis_client.lpush(cache_key, json.dumps(memory_entry, default=str))
            await self.redis_client.expire(cache_key, 3600)  # 1 hour cache

            # Redis keeps the short session window; MongoDB keeps long-term memory.
            await self.redis_client.ltrim(cache_key, 0, settings.MEMORY_LAST_K - 1)
            await self._update_session_summary(query.session_id)

            logger.debug(f"Added interaction to memory: {query.query_id}")

        except Exception as e:
            logger.error(f"Failed to add interaction to memory: {str(e)}")

    async def get_relevant_memory(
        self,
        query: Query,
        k: int = 5
    ) -> str:
        """
        Get relevant memory context for the query

        Args:
            query: Current query
            k: Number of recent interactions to retrieve

        Returns:
            Formatted memory context string
        """
        try:
            if not query.session_id:
                return ""

            # Short-term memory: last-k turns from Redis for low-latency injection.
            cache_key = f"memory:{query.session_id}:recent"
            cached_memory = await self.redis_client.lrange(cache_key, 0, k-1)

            memory_entries = []
            if cached_memory:
                # Use cached memory
                memory_entries = [json.loads(entry) for entry in cached_memory]
            else:
                # Fetch from database
                cursor = self.memory_collection.find(
                    {"session_id": query.session_id}
                ).sort("timestamp", -1).limit(k)

                memory_entries = await cursor.to_list(length=k)

            if not memory_entries:
                return ""

            long_term_summary = await self._get_long_term_summary(query.session_id)

            # Format memory context
            memory_parts = []
            if long_term_summary:
                memory_parts.append("Long-term session summary:")
                memory_parts.append(long_term_summary)
                memory_parts.append("")

            memory_parts.append(f"Recent session turns (last {len(memory_entries)}):")
            for i, entry in enumerate(memory_entries):
                memory_parts.append(f"Previous Interaction {i+1}:")
                memory_parts.append(f"Q: {entry['query_text']}")
                memory_parts.append(f"A: {entry['response'][:200]}..." if len(entry['response']) > 200 else f"A: {entry['response']}")
                memory_parts.append("")

            memory_context = "\n".join(memory_parts).strip()

            logger.debug(f"Retrieved {len(memory_entries)} memory entries for session {query.session_id}")
            return memory_context

        except Exception as e:
            logger.error(f"Failed to retrieve memory: {str(e)}")
            return ""

    async def _update_session_summary(self, session_id: Optional[str]) -> None:
        if not session_id:
            return

        try:
            cursor = self.memory_collection.find(
                {"session_id": session_id}
            ).sort("timestamp", -1).skip(settings.MEMORY_LAST_K).limit(20)
            older_entries = await cursor.to_list(length=20)
            if not older_entries:
                return

            topic_snippets = [entry.get("query_text", "") for entry in older_entries[:8]]
            summary = " | ".join(snippet[:120] for snippet in topic_snippets if snippet)
            await self.memory_collection.update_one(
                {"session_id": session_id, "memory_type": "session_summary"},
                {
                    "$set": {
                        "session_id": session_id,
                        "memory_type": "session_summary",
                        "summary": summary,
                        "updated_at": datetime.utcnow(),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to update long-term session summary: {str(e)}")

    async def _get_long_term_summary(self, session_id: str) -> str:
        try:
            summary = await self.memory_collection.find_one(
                {"session_id": session_id, "memory_type": "session_summary"}
            )
            return summary.get("summary", "") if summary else ""
        except Exception as e:
            logger.warning(f"Failed to get long-term session summary: {str(e)}")
            return ""

    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary of conversation session

        Args:
            session_id: Session identifier

        Returns:
            Session summary statistics
        """
        try:
            pipeline = [
                {"$match": {"session_id": session_id}},
                {"$group": {
                    "_id": "$session_id",
                    "total_interactions": {"$sum": 1},
                    "avg_response_length": {"$avg": {"$strLenCP": "$response"}},
                    "last_interaction": {"$max": "$timestamp"},
                    "topics": {"$addToSet": "$query_text"}
                }}
            ]

            result = await self.memory_collection.aggregate(pipeline).to_list(length=1)

            if result:
                summary = result[0]
                summary["session_id"] = summary.pop("_id")
                return summary

            return {
                "session_id": session_id,
                "total_interactions": 0,
                "avg_response_length": 0,
                "last_interaction": None,
                "topics": []
            }

        except Exception as e:
            logger.error(f"Failed to get session summary: {str(e)}")
            return {"error": str(e)}
