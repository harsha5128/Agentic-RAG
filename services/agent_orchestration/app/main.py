"""
Agent Orchestration Service
Manages multi-agent workflows and state coordination
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from typing import Dict, Optional, List
from datetime import datetime
import sys
from pathlib import Path
from langgraph.graph import StateGraph, END
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    from langgraph.checkpoint import SqliteSaver
from langchain.chat_models import ChatOpenAI
from langchain.tools import tool
import redis.asyncio as redis
import json
from pymongo import MongoClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.config import settings
from common.observability import setup_logging, setup_tracing, get_logger
from common.schemas import WorkflowState, AgentState, AgentRole

logger = get_logger(__name__)


class AgentOrchestrationService:
    """Service for orchestrating multi-agent workflows"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.TEMPERATURE,
        )
        self.redis_client = None
        self.mongo_client = None
        self.workflow_graph = None
        self.checkpointer = None
    
    async def initialize(self):
        """Initialize service"""
        self.redis_client = await redis.from_url(settings.redis_url, decode_responses=True)
        self.mongo_client = MongoClient(settings.MONGODB_URI)
        self.db = self.mongo_client[settings.MONGODB_DATABASE]
        self.workflows_collection = self.db['workflows']
        
        # Initialize workflow graph with checkpointing
        self.checkpointer = SqliteSaver(":memory:")
        self.workflow_graph = self._build_workflow_graph()
        
        logger.info("Agent Orchestration Service initialized")
    
    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.mongo_client:
            self.mongo_client.close()
    
    def _build_workflow_graph(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(WorkflowState)
        
        # Define nodes
        workflow.add_node("initialize", self._initialize_agents)
        workflow.add_node("retrieve", self._retrieve_documents)
        workflow.add_node("analyze", self._analyze_documents)
        workflow.add_node("synthesize", self._synthesize_answer)
        workflow.add_node("evaluate", self._evaluate_result)
        
        # Define edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "retrieve")
        workflow.add_edge("retrieve", "analyze")
        workflow.add_edge("analyze", "synthesize")
        workflow.add_edge("synthesize", "evaluate")
        workflow.add_edge("evaluate", END)
        
        # Compile with checkpointing
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _initialize_agents(self, state: WorkflowState) -> WorkflowState:
        """Initialize agent states"""
        agents = {
            "retriever": AgentState(
                agent_id="retriever-1",
                agent_role=AgentRole.RETRIEVER,
                status="active",
                tools_available=["vector_search", "metadata_filter"],
            ),
            "analyzer": AgentState(
                agent_id="analyzer-1",
                agent_role=AgentRole.ANALYZER,
                status="active",
                tools_available=["extract_entities", "summarize"],
            ),
            "synthesizer": AgentState(
                agent_id="synthesizer-1",
                agent_role=AgentRole.SYNTHESIZER,
                status="active",
                tools_available=["generate_response", "format_output"],
            ),
        }
        state.agent_states = agents
        state.current_stage = "retrieval"
        return state
    
    async def _retrieve_documents(self, state: WorkflowState) -> WorkflowState:
        """Retrieve documents"""
        # TODO: Call retrieval service
        logger.info("Retrieving documents")
        state.current_stage = "analysis"
        return state
    
    async def _analyze_documents(self, state: WorkflowState) -> WorkflowState:
        """Analyze retrieved documents"""
        logger.info("Analyzing documents")
        state.current_stage = "synthesis"
        return state
    
    async def _synthesize_answer(self, state: WorkflowState) -> WorkflowState:
        """Synthesize final answer"""
        logger.info("Synthesizing answer")
        
        # Use LLM to generate response
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant answering questions based on provided documents.",
            },
            {
                "role": "user",
                "content": state.query.query_text,
            }
        ]
        
        response = self.llm.invoke(messages)
        state.final_answer = response.content
        state.current_stage = "evaluation"
        
        return state
    
    async def _evaluate_result(self, state: WorkflowState) -> WorkflowState:
        """Evaluate result quality"""
        logger.info("Evaluating result")
        state.current_stage = "complete"
        return state
    
    async def execute_workflow(self, workflow_state: WorkflowState) -> WorkflowState:
        """
        Execute multi-agent workflow
        
        Args:
            workflow_state: Initial workflow state
        
        Returns:
            Final workflow state with results
        """
        try:
            # Run workflow
            final_state = self.workflow_graph.invoke(workflow_state)
            
            # Save to database
            self.workflows_collection.insert_one({
                "workflow_id": workflow_state.workflow_id,
                "query": workflow_state.query.dict(),
                "final_answer": final_state.final_answer,
                "created_at": datetime.utcnow(),
            })
            
            return final_state
            
        except Exception as e:
            logger.error(f"Error executing workflow: {str(e)}")
            raise


orchestration_service = AgentOrchestrationService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    await orchestration_service.initialize()
    logger.info("Agent Orchestration Service started")
    yield
    await orchestration_service.close()
    logger.info("Agent Orchestration Service shutdown")


app = FastAPI(
    title="Agent Orchestration Service",
    description="Orchestrates multi-agent workflows",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "agent-orchestration",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/execute-workflow")
async def execute_workflow(workflow_state: WorkflowState):
    """Execute multi-agent workflow"""
    result = await orchestration_service.execute_workflow(workflow_state)
    return {
        "status": "success",
        "workflow_id": result.workflow_id,
        "final_answer": result.final_answer,
        "token_count": result.token_count,
    }


if __name__ == "__main__":
    import uvicorn
    setup_logging(settings.LOG_LEVEL)
    setup_tracing(settings.SERVICE_NAME, settings.ENVIRONMENT)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
