"""
Agent Orchestrator - Integrates with Agent Orchestration Service for complex queries
"""

import aiohttp
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from common.config import settings
from common.observability import get_logger
from common.schemas import Query

logger = get_logger(__name__)


@dataclass
class AgentResult:
    """Result from agent orchestration"""
    response: str
    thoughts: str
    agent_used: str
    confidence: float
    processing_time: float
    tool_calls: List[Dict[str, Any]] = None


class AgentOrchestrator:
    """Handles integration with Agent Orchestration Service"""

    def __init__(self, agent_service_url: str):
        self.agent_service_url = agent_service_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def orchestrate_query(
        self,
        query: Query,
        context: Dict[str, Any],
        memory: str = ""
    ) -> AgentResult:
        """
        Orchestrate query using multi-agent system

        Args:
            query: The query to process
            context: Retrieved and refined context
            memory: Conversation memory

        Returns:
            Agent processing result
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Prepare request payload
            payload = {
                "query": query.dict(),
                "context": context,
                "memory": memory,
                "enable_tools": True,
                "max_iterations": 3,
            }

            # Call agent orchestration service
            async with self.session.post(
                f"{self.agent_service_url}/orchestrate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)  # 60 second timeout
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Agent orchestration failed: {response.status} - {error_text}")
                    raise Exception(f"Agent service error: {response.status}")

                result_data = await response.json()

                # Parse result
                agent_result = AgentResult(
                    response=result_data.get("response", ""),
                    thoughts=result_data.get("thoughts", ""),
                    agent_used=result_data.get("agent_used", "unknown"),
                    confidence=result_data.get("confidence", 0.5),
                    processing_time=result_data.get("processing_time", 0.0),
                    tool_calls=result_data.get("tool_calls", [])
                )

                logger.info(f"Agent orchestration completed for query {query.query_id}: agent={agent_result.agent_used}, confidence={agent_result.confidence}")
                return agent_result

        except aiohttp.ClientError as e:
            logger.error(f"Agent orchestration network error: {str(e)}")
            # Return fallback result
            return AgentResult(
                response="I apologize, but the agent orchestration service is currently unavailable. Please try again later.",
                thoughts="Agent service unavailable - using fallback response",
                agent_used="fallback",
                confidence=0.1,
                processing_time=0.0
            )

        except Exception as e:
            logger.error(f"Agent orchestration failed: {str(e)}")
            # Return fallback result
            return AgentResult(
                response="I encountered an error while processing your query with advanced reasoning. Please try rephrasing your question.",
                thoughts=f"Agent orchestration error: {str(e)}",
                agent_used="error_fallback",
                confidence=0.2,
                processing_time=0.0
            )
