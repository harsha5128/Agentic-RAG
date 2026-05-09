"""
Prompt Builder - Constructs optimized prompts for LLM calls
"""

from typing import Dict, Any
import redis.asyncio as redis

from common.config import settings
from common.observability import get_logger
from common.schemas import Query

try:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:  # pragma: no cover - keeps service usable in lean installs
    ChatPromptTemplate = None
    MessagesPlaceholder = None

logger = get_logger(__name__)


class PromptTemplate:
    """Template for LLM prompts"""

    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        metadata: Dict[str, Any] = None,
        chat_prompt: Any = None,
    ):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.metadata = metadata or {}
        self.chat_prompt = chat_prompt


class PromptBuilder:
    """Builds optimized prompts for different query types"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def build_prompt(
        self,
        query: Query,
        context: Dict[str, Any],
        memory: str = "",
        oos_detected: bool = False
    ) -> PromptTemplate:
        """
        Build complete prompt for LLM

        Args:
            query: The query object
            context: Refined context dictionary
            memory: Memory context string
            oos_detected: Whether query is out of scope

        Returns:
            Complete prompt template
        """
        try:
            if oos_detected:
                # Out of scope response
                system_prompt = """You are a helpful assistant. The user's query appears to be outside the scope of the available documents.

Please respond politely explaining that you can only answer questions based on the provided document collection."""

                user_prompt = f"""Query: {query.query_text}

I apologize, but I can only provide answers based on the documents in our knowledge base. Your question doesn't appear to be related to the available content.

Please try rephrasing your question or ask about topics covered in our documentation."""

            else:
                # Standard RAG prompt
                system_prompt = f"""You are an expert assistant that answers questions based on provided documents.

INSTRUCTIONS:
- Answer questions accurately using ONLY the provided context
- If the answer isn't in the context, say "I don't have enough information to answer this question based on the available documents"
- Be concise but comprehensive
- Include specific references to document sources when relevant
- Format your response clearly with proper structure
- Use bullet points or numbered lists when appropriate

CONTEXT QUALITY: The provided context has been optimized and filtered for relevance."""

                # Build user prompt with context and memory
                user_prompt_parts = []

                # Add memory context if available
                if memory and memory.strip():
                    user_prompt_parts.append(f"CONVERSATION HISTORY:\n{memory}\n")

                # Add current query
                user_prompt_parts.append(f"CURRENT QUESTION: {query.query_text}\n")

                # Add context
                if context.get("context"):
                    user_prompt_parts.append(f"DOCUMENT CONTEXT:\n{context['context']}\n")

                # Add source information
                if context.get("sources"):
                    sources_info = "\n".join([
                        f"- {src['file_name']} (relevance: {src['score']:.3f})"
                        for src in context["sources"][:3]  # Top 3 sources
                    ])
                    user_prompt_parts.append(f"SOURCE DOCUMENTS:\n{sources_info}\n")

                user_prompt_parts.append("Please provide a comprehensive answer based on the above context:")

                user_prompt = "\n".join(user_prompt_parts)

            chat_prompt = self._build_langchain_chat_prompt(system_prompt, user_prompt, memory)

            # Create prompt template
            prompt = PromptTemplate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                chat_prompt=chat_prompt,
                metadata={
                    "query_id": query.query_id,
                    "context_docs": len(context.get("sources", [])),
                    "context_length": len(context.get("context", "")),
                    "has_memory": bool(memory and memory.strip()),
                    "oos_detected": oos_detected,
                    "template_version": "2.1-langchain-chat-template",
                    "uses_langchain_chat_template": chat_prompt is not None,
                }
            )

            logger.debug(f"Built prompt for query {query.query_id}: {len(system_prompt)} + {len(user_prompt)} chars")
            return prompt

        except Exception as e:
            logger.error(f"Prompt building failed: {str(e)}")
            # Return basic fallback prompt
            return PromptTemplate(
                system_prompt="You are a helpful assistant.",
                user_prompt=f"Please answer: {query.query_text}",
                metadata={"error": str(e), "fallback": True}
            )

    def _build_langchain_chat_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        memory: str,
    ) -> Any:
        """
        Build a LangChain ChatPromptTemplate while retaining plain strings for
        services that call OpenAI directly.
        """
        if not ChatPromptTemplate:
            return None

        messages = [("system", system_prompt)]
        if memory and memory.strip() and MessagesPlaceholder:
            messages.append(MessagesPlaceholder(variable_name="history"))
        messages.append(("human", "{user_prompt}"))

        return ChatPromptTemplate.from_messages(messages).partial(user_prompt=user_prompt)
