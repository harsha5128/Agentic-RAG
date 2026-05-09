"""
Response Formatter - Post-processes and formats LLM responses
"""

from typing import List, Dict, Any
import re

from common.config import settings
from common.observability import get_logger
from common.schemas import Query, RetrievedDocument

logger = get_logger(__name__)


class FormattedResponse:
    """Formatted response with metadata"""

    def __init__(
        self,
        final_answer: str,
        confidence_score: float,
        token_usage: Dict[str, int],
        sources: List[Dict[str, Any]] = None,
        processing_steps: List[str] = None
    ):
        self.final_answer = final_answer
        self.confidence_score = confidence_score
        self.token_usage = token_usage
        self.sources = sources or []
        self.processing_steps = processing_steps or []


class ResponseFormatter:
    """Formats and post-processes LLM responses"""

    def __init__(self):
        pass

    async def format_response(
        self,
        raw_response: str,
        query: Query,
        retrieved_docs: List[RetrievedDocument]
    ) -> FormattedResponse:
        """
        Format and post-process LLM response

        - Clean and structure the response
        - Calculate confidence score
        - Extract source references
        - Validate response quality
        """
        try:
            # Clean the response
            cleaned_response = self._clean_response(raw_response)

            # Calculate confidence score
            confidence_score = self._calculate_confidence(
                cleaned_response, query, retrieved_docs
            )

            # Extract source information
            sources = self._extract_sources(cleaned_response, retrieved_docs)

            # Estimate token usage (rough approximation)
            token_usage = self._estimate_token_usage(cleaned_response)

            # Create formatted response
            formatted = FormattedResponse(
                final_answer=cleaned_response,
                confidence_score=confidence_score,
                token_usage=token_usage,
                sources=sources,
                processing_steps=[
                    "response_cleaning",
                    "confidence_scoring",
                    "source_extraction",
                    "token_estimation"
                ]
            )

            logger.debug(f"Formatted response for query {query.query_id}: {len(cleaned_response)} chars, confidence {confidence_score:.2f}")
            return formatted

        except Exception as e:
            logger.error(f"Response formatting failed: {str(e)}")
            # Return basic formatted response
            return FormattedResponse(
                final_answer=raw_response,
                confidence_score=0.5,
                token_usage={"estimated": len(raw_response.split())},
                sources=[],
                processing_steps=["error_fallback"]
            )

    def _clean_response(self, response: str) -> str:
        """Clean and normalize the response"""
        if not response:
            return "I apologize, but I couldn't generate a response."

        # Remove excessive whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', response.strip())

        # Fix common formatting issues
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)

        # Ensure proper sentence endings
        if not cleaned.endswith(('.', '!', '?', ':')):
            cleaned += '.'

        return cleaned

    def _calculate_confidence(
        self,
        response: str,
        query: Query,
        retrieved_docs: List[RetrievedDocument]
    ) -> float:
        """
        Calculate confidence score based on multiple factors

        Factors:
        - Response length vs query complexity
        - Source document relevance scores
        - Response specificity
        - Presence of uncertainty markers
        """
        try:
            confidence = 0.5  # Base confidence

            # Factor 1: Response length (longer responses tend to be more confident)
            response_length = len(response.split())
            if response_length > 50:
                confidence += 0.1
            elif response_length < 10:
                confidence -= 0.2

            # Factor 2: Document relevance scores
            if retrieved_docs:
                avg_score = sum(doc.score for doc in retrieved_docs) / len(retrieved_docs)
                confidence += (avg_score - 0.5) * 0.4  # Scale relevance impact

            # Factor 3: Uncertainty markers
            uncertainty_markers = [
                "i don't know", "unclear", "not sure", "cannot determine",
                "insufficient information", "not enough data"
            ]

            response_lower = response.lower()
            uncertainty_count = sum(1 for marker in uncertainty_markers if marker in response_lower)

            if uncertainty_count > 0:
                confidence -= min(0.3, uncertainty_count * 0.1)

            # Factor 4: Query complexity (longer queries might be harder)
            query_length = len(query.query_text.split())
            if query_length > 20:
                confidence -= 0.1

            # Clamp to [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            return round(confidence, 3)

        except Exception as e:
            logger.error(f"Confidence calculation failed: {str(e)}")
            return 0.5

    def _extract_sources(
        self,
        response: str,
        retrieved_docs: List[RetrievedDocument]
    ) -> List[Dict[str, Any]]:
        """Extract and format source information"""
        try:
            sources = []

            for doc in retrieved_docs[:5]:  # Top 5 sources
                source_info = {
                    "document_id": doc.document_id,
                    "file_name": doc.file_name,
                    "chunk_index": doc.chunk_index,
                    "relevance_score": doc.score,
                    "content_preview": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                }
                sources.append(source_info)

            return sources

        except Exception as e:
            logger.error(f"Source extraction failed: {str(e)}")
            return []

    def _estimate_token_usage(self, response: str) -> Dict[str, int]:
        """Estimate token usage (rough approximation)"""
        try:
            # Rough approximation: 1 token ≈ 0.75 words for English text
            word_count = len(response.split())
            estimated_tokens = int(word_count * 1.33)  # Conservative estimate

            return {
                "estimated_completion_tokens": estimated_tokens,
                "estimated_total_tokens": estimated_tokens,  # Simplified
                "method": "word_count_estimation"
            }

        except Exception as e:
            logger.error(f"Token estimation failed: {str(e)}")
            return {"estimated_completion_tokens": 0, "method": "failed"}