"""
Query Processor - Handles query cleaning, normalization, and rewriting
"""

import re
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis

from common.config import settings
from common.observability import get_logger
from common.schemas import Query

logger = get_logger(__name__)


class QueryProcessor:
    """Handles query preprocessing and optimization"""

    def __init__(self, mongo_client: AsyncIOMotorClient, redis_client: redis.Redis):
        self.mongo_client = mongo_client
        self.redis_client = redis_client
        self.db = mongo_client[settings.MONGODB_DATABASE]

    async def clean_and_normalize(self, query: Query) -> Query:
        """
        Clean and normalize query text

        - Remove extra whitespace
        - Fix common typos
        - Normalize punctuation
        - Remove potentially harmful content
        """
        try:
            # Clean text
            cleaned_text = query.query_text.strip()
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Multiple spaces to single
            cleaned_text = re.sub(r'[^\w\s.,!?-]', '', cleaned_text)  # Remove special chars except basic punctuation

            # Basic security filtering
            harmful_patterns = [
                r'<script[^>]*>.*?</script>',  # Script tags
                r'javascript:',  # JavaScript URLs
                r'on\w+\s*=',  # Event handlers
            ]

            for pattern in harmful_patterns:
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

            # Create cleaned query
            cleaned_query = Query(
                query_id=query.query_id,
                query_text=cleaned_text,
                user_id=query.user_id,
                session_id=query.session_id,
                filters=query.filters,
                metadata={
                    **query.metadata,
                    "original_query": query.query_text,
                    "cleaned": True,
                }
            )

            logger.debug(f"Cleaned query: {query.query_text[:50]}... -> {cleaned_text[:50]}...")
            return cleaned_query

        except Exception as e:
            logger.error(f"Query cleaning failed: {str(e)}")
            return query  # Return original if cleaning fails

    async def rewrite_query(self, query: Query) -> Query:
        """
        Optionally rewrite query for better retrieval

        - Expand abbreviations
        - Add context keywords
        - Improve clarity
        """
        try:
            rewritten_text = query.query_text

            # Simple rule-based rewriting
            rewrite_rules = {
                r'\bAI\b': 'artificial intelligence',
                r'\bML\b': 'machine learning',
                r'\bRAG\b': 'Retrieval Augmented Generation',
                r'\bLLM\b': 'Large Language Model',
                r'\bAPI\b': 'Application Programming Interface',
            }

            for pattern, replacement in rewrite_rules.items():
                rewritten_text = re.sub(pattern, replacement, rewritten_text, flags=re.IGNORECASE)

            # Check if rewriting actually changed anything
            if rewritten_text != query.query_text:
                rewritten_query = Query(
                    query_id=f"{query.query_id}_rewritten",
                    query_text=rewritten_text,
                    user_id=query.user_id,
                    session_id=query.session_id,
                    filters=query.filters,
                    metadata={
                        **query.metadata,
                        "original_query": query.query_text,
                        "rewritten": True,
                    }
                )

                logger.debug(f"Rewrote query: {query.query_text[:50]}... -> {rewritten_text[:50]}...")
                return rewritten_query

            return query

        except Exception as e:
            logger.error(f"Query rewriting failed: {str(e)}")
            return query  # Return original if rewriting fails