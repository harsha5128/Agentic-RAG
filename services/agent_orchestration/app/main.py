"""
Agent Orchestration Service

Uses LangGraph for the main workflow, keeps small custom abstractions as learning
notes/fallbacks, and exposes simple tool-calling, MCP-style local tools, CrewAI
role-play specs, and AutoGen-style conversation specs.
"""

import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypedDict

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from common.base_service import BaseService
from common.observability import get_logger
from common.schemas import AgentRole, AgentState, Query, WorkflowState
from common.exceptions import AgentOrchestrationError, ErrorCode, ToolExecutionError

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - lets the service compile without optional deps
    END = None
    StateGraph = None

try:
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables import RunnableLambda
except ImportError:  # pragma: no cover
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    RunnableLambda = None

try:
    from crewai import Agent as CrewAIAgent
except ImportError:  # pragma: no cover
    CrewAIAgent = None

try:
    import autogen
except ImportError:  # pragma: no cover
    autogen = None


logger = get_logger(__name__)


class OrchestrationRequest(BaseModel):
    """Request payload used by query-processing for agentic reasoning."""

    query: Dict[str, Any]
    context: Dict[str, Any] = Field(default_factory=dict)
    memory: str = ""
    enable_tools: bool = True
    max_iterations: int = 3


class ToolCallRequest(BaseModel):
    """Tool call request for direct testing and MCP-style routing."""

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowState(TypedDict, total=False):
    """LangGraph state. Dict state avoids coupling LangGraph to Pydantic internals."""

    workflow_id: str
    query: Dict[str, Any]
    context: Dict[str, Any]
    memory: str
    agent_states: Dict[str, Dict[str, Any]]
    current_stage: str
    intermediate_results: Dict[str, Any]
    final_answer: str
    tool_calls: List[Dict[str, Any]]
    error_messages: List[str]
    token_count: int


class Tool:
    """Small custom tool wrapper used by both LangGraph and the MCP-style adapter."""

    def __init__(
        self,
        tool_id: str,
        tool_name: str,
        description: str,
        available_for_roles: List[AgentRole],
        execute_fn: Callable[..., Coroutine[Any, Any, Any]],
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
    ):
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.description = description
        self.available_for_roles = available_for_roles
        self.execute_fn = execute_fn
        self.input_schema = input_schema
        self.output_schema = output_schema

    async def execute(self, **kwargs) -> Any:
        return await self.execute_fn(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "description": self.description,
            "available_for_roles": [role.value for role in self.available_for_roles],
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class AgentToolRegistry:
    """Registry for function/tool calling."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.tool_name] = tool
        logger.info(f"Registered tool: {tool.tool_name}")

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        tool = self.tools.get(tool_name)
        if not tool:
            raise ToolExecutionError(
                ErrorCode.TOOL_REGISTRY_ERROR,
                f"Tool not found: {tool_name}",
            )
        return await tool.execute(**kwargs)

    def as_openai_tools(self) -> List[Dict[str, Any]]:
        """Expose tools in OpenAI function-calling shape."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.tool_name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.tools.values()
        ]


class LocalMCPProvider:
    """
    Minimal MCP-style local provider.

    This is not a networked MCP server. It intentionally mirrors the provider/tool
    shape so the project can later swap this adapter for a real MCP SDK transport.
    """

    def __init__(self, provider_id: str, registry: AgentToolRegistry):
        self.provider_id = provider_id
        self.registry = registry

    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        return await self.registry.execute_tool(tool_name, **kwargs)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self.registry.tools.values()]


class MCPProtocolHandler:
    """Routes MCP-style tool calls to registered providers."""

    def __init__(self):
        self.providers: Dict[str, LocalMCPProvider] = {}

    def register_provider(self, provider: LocalMCPProvider) -> None:
        self.providers[provider.provider_id] = provider

    async def call_tool(self, provider_id: str, tool_name: str, **kwargs) -> Any:
        provider = self.providers.get(provider_id)
        if not provider:
            raise AgentOrchestrationError(
                ErrorCode.MCP_PROTOCOL_ERROR,
                f"MCP provider not found: {provider_id}",
            )
        return await provider.call_tool(tool_name, **kwargs)


class AgentRolePlayCatalog:
    """CrewAI/AutoGen learning specs without forcing those frameworks at runtime."""

    def __init__(self):
        self.roles = [
            {
                "role": "Retriever",
                "goal": "Find the most relevant evidence from retrieved chunks.",
                "backstory": "A search specialist that cares about source coverage and recall.",
            },
            {
                "role": "Analyst",
                "goal": "Compare evidence, identify contradictions, and extract reasoning points.",
                "backstory": "A careful reasoning agent that separates facts from guesses.",
            },
            {
                "role": "Synthesizer",
                "goal": "Write a grounded answer using only the evidence passed in state.",
                "backstory": "A concise answer writer that explains uncertainty clearly.",
            },
        ]

    def crewai_specs(self) -> Dict[str, Any]:
        if CrewAIAgent:
            agents = [
                CrewAIAgent(
                    role=role["role"],
                    goal=role["goal"],
                    backstory=role["backstory"],
                    allow_delegation=False,
                    verbose=False,
                )
                for role in self.roles
            ]
            return {
                "framework": "crewai",
                "available": True,
                "agents": [agent.role for agent in agents],
                "note": "Specs are instantiated; actual crew execution can be added around a paid/local LLM.",
            }
        return {
            "framework": "crewai",
            "available": False,
            "agents": self.roles,
            "note": "crewai is not importable in this environment, so role specs are returned as plain data.",
        }

    def autogen_specs(self) -> Dict[str, Any]:
        return {
            "framework": "autogen",
            "available": autogen is not None,
            "agents": [
                {"name": "retriever_proxy", "system_message": self.roles[0]["goal"]},
                {"name": "analyst_assistant", "system_message": self.roles[1]["goal"]},
                {"name": "synthesizer_assistant", "system_message": self.roles[2]["goal"]},
            ],
            "note": "AutoGen conversation specs are present for learning; execution is deferred to avoid requiring live LLM credentials during service startup.",
        }


class LangGraphWorkflowOrchestrator:
    """LangGraph-first workflow with a sequential fallback."""

    def __init__(self, tool_registry: AgentToolRegistry):
        self.tool_registry = tool_registry
        self.workflow_graph = self._build_graph() if StateGraph else None

    def _build_graph(self):
        graph = StateGraph(AgentWorkflowState)
        graph.add_node("initialize", self._initialize_agents)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("analyze", self._analyze)
        graph.add_node("tool_use", self._tool_use)
        graph.add_node("synthesize", self._synthesize)
        graph.add_node("evaluate", self._evaluate)

        graph.set_entry_point("initialize")
        graph.add_edge("initialize", "retrieve")
        graph.add_edge("retrieve", "analyze")
        graph.add_edge("analyze", "tool_use")
        graph.add_edge("tool_use", "synthesize")
        graph.add_edge("synthesize", "evaluate")
        graph.add_edge("evaluate", END)
        return graph.compile()

    async def execute(self, state: AgentWorkflowState) -> AgentWorkflowState:
        if self.workflow_graph:
            return await self.workflow_graph.ainvoke(state)

        for node in [
            self._initialize_agents,
            self._retrieve,
            self._analyze,
            self._tool_use,
            self._synthesize,
            self._evaluate,
        ]:
            state = await node(state)
        return state

    async def _initialize_agents(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "initialize"
        state["agent_states"] = {
            "retriever": self._agent_state("retriever-1", AgentRole.RETRIEVER),
            "analyzer": self._agent_state("analyzer-1", AgentRole.ANALYZER),
            "executor": self._agent_state("executor-1", AgentRole.EXECUTOR),
            "synthesizer": self._agent_state("synthesizer-1", AgentRole.SYNTHESIZER),
        }
        state.setdefault("intermediate_results", {})
        state.setdefault("tool_calls", [])
        state.setdefault("error_messages", [])
        return state

    async def _retrieve(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "retrieve"
        context = state.get("context", {})
        sources = context.get("sources", [])
        state["intermediate_results"]["retrieval"] = {
            "source_count": len(sources),
            "status": "context_received",
        }
        return state

    async def _analyze(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "analyze"
        context_text = state.get("context", {}).get("context", "")
        query_text = state.get("query", {}).get("query_text", "")
        out_of_context = not bool(context_text.strip())
        state["intermediate_results"]["analysis"] = {
            "query_terms": self._keywords(query_text),
            "context_terms": self._keywords(context_text)[:12],
            "has_context": not out_of_context,
            "route": "react_tools" if out_of_context else "grounded_rag",
        }
        state["intermediate_results"]["react_trace"] = [
            {
                "thought": "Check whether retrieved context is enough to answer.",
                "action": "inspect_context",
                "observation": "No retrieved context available." if out_of_context else "Retrieved context is available.",
            }
        ]
        return state

    async def _tool_use(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "tool_use"
        context_text = state.get("context", {}).get("context", "")
        summary = await self.tool_registry.execute_tool(
            "summarize_context",
            text=context_text,
            max_sentences=3,
        )
        entities = await self.tool_registry.execute_tool("extract_keywords", text=context_text)
        state["intermediate_results"].setdefault("react_trace", []).extend(
            [
                {
                    "thought": "Use tools to compress evidence before synthesis.",
                    "action": "summarize_context",
                    "observation": summary or "No evidence summary produced.",
                },
                {
                    "thought": "Extract key terms to support grounding and source comparison.",
                    "action": "extract_keywords",
                    "observation": entities,
                },
            ]
        )
        state["tool_calls"] = [
            {"tool": "summarize_context", "result": summary},
            {"tool": "extract_keywords", "result": entities},
        ]
        state["intermediate_results"]["tool_use"] = {
            "summary": summary,
            "keywords": entities,
        }
        return state

    async def _synthesize(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "synthesize"
        query_text = state.get("query", {}).get("query_text", "")
        summary = state["intermediate_results"].get("tool_use", {}).get("summary", "")
        memory = state.get("memory", "")

        if ChatPromptTemplate and RunnableLambda:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "Answer only from the provided RAG context. Be concise and grounded."),
                    MessagesPlaceholder(variable_name="history") if MessagesPlaceholder else ("system", ""),
                    ("human", "Question: {question}\n\nMemory:\n{memory}\n\nContext summary:\n{summary}"),
                ]
            )
            render = RunnableLambda(lambda value: prompt.invoke(value).to_string())
            rendered_prompt = await render.ainvoke(
                {
                    "question": query_text,
                    "memory": memory,
                    "summary": summary,
                    "history": [],
                }
            )
            state["intermediate_results"]["langchain_prompt"] = rendered_prompt

        if summary:
            state["final_answer"] = f"Based on the retrieved context: {summary}"
        else:
            state["final_answer"] = (
                "I do not have enough retrieved context to answer this safely. "
                "Please upload or retrieve relevant documents, or ask a question covered by the indexed knowledge base."
            )
        state["token_count"] = len(state["final_answer"].split())
        return state

    async def _evaluate(self, state: AgentWorkflowState) -> AgentWorkflowState:
        state["current_stage"] = "complete"
        answer = state.get("final_answer", "")
        state["intermediate_results"]["evaluation"] = {
            "has_answer": bool(answer.strip()),
            "estimated_words": len(answer.split()),
            "grounding_mode": "context_only",
        }
        return state

    def _agent_state(self, agent_id: str, role: AgentRole) -> Dict[str, Any]:
        tools = [
            tool.tool_name
            for tool in self.tool_registry.tools.values()
            if role in tool.available_for_roles
        ]
        return AgentState(
            agent_id=agent_id,
            agent_role=role,
            status="idle",
            tools_available=tools,
        ).model_dump()

    def _keywords(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        seen = []
        for word in words:
            if word not in seen:
                seen.append(word)
        return seen[:20]


class AgentOrchestrationService(BaseService):
    """Service facade around LangGraph, tools, role-play specs, and MCP adapter."""

    def __init__(self):
        super().__init__("agent-orchestration-service")
        self.tool_registry = AgentToolRegistry()
        self.mcp_handler = MCPProtocolHandler()
        self.role_catalog = AgentRolePlayCatalog()
        self.workflows: Dict[str, AgentWorkflowState] = {}
        self.session_memory: Dict[str, List[Dict[str, str]]] = {}
        self._setup_default_tools()
        self.mcp_handler.register_provider(LocalMCPProvider("local-rag-tools", self.tool_registry))
        self.orchestrator = LangGraphWorkflowOrchestrator(self.tool_registry)

    async def _initialize_dependencies(self) -> None:
        self.register_dependency("langgraph", lambda: self._check_langgraph())

    async def _check_langgraph(self) -> bool:
        return self.orchestrator.workflow_graph is not None

    def _setup_default_tools(self) -> None:
        self.tool_registry.register_tool(
            Tool(
                tool_id="tool-summarize-context",
                tool_name="summarize_context",
                description="Summarize retrieved context into a few evidence-focused sentences.",
                available_for_roles=[AgentRole.EXECUTOR, AgentRole.SYNTHESIZER],
                execute_fn=self._summarize_context,
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "max_sentences": {"type": "integer", "default": 3},
                    },
                    "required": ["text"],
                },
                output_schema={"type": "string"},
            )
        )
        self.tool_registry.register_tool(
            Tool(
                tool_id="tool-extract-keywords",
                tool_name="extract_keywords",
                description="Extract simple keywords/entities from retrieved context.",
                available_for_roles=[AgentRole.ANALYZER, AgentRole.EXECUTOR],
                execute_fn=self._extract_keywords,
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                output_schema={"type": "array", "items": {"type": "string"}},
            )
        )

    async def _summarize_context(self, text: str, max_sentences: int = 3) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        selected = [sentence.strip() for sentence in sentences if sentence.strip()][:max_sentences]
        return " ".join(selected)

    async def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
        stopwords = {"this", "that", "with", "from", "have", "will", "based", "context"}
        unique = []
        for word in words:
            if word not in stopwords and word not in unique:
                unique.append(word)
        return unique[:12]

    async def create_workflow(self, query: Query) -> str:
        workflow_id = str(uuid.uuid4())
        self.workflows[workflow_id] = {
            "workflow_id": workflow_id,
            "query": query.model_dump(),
            "context": {},
            "memory": "",
            "current_stage": "created",
            "intermediate_results": {},
            "tool_calls": [],
            "error_messages": [],
        }
        return workflow_id

    async def get_workflow_state(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise AgentOrchestrationError(
                ErrorCode.AGENT_EXECUTION_FAILED,
                f"Workflow not found: {workflow_id}",
            )
        return workflow

    async def execute_workflow_stage(self, workflow_id: str, stage: str) -> Dict[str, Any]:
        workflow = await self.get_workflow_state(workflow_id)
        workflow["current_stage"] = stage
        return {"status": "success", "workflow_id": workflow_id, "stage": stage}

    async def orchestrate(self, request: OrchestrationRequest) -> Dict[str, Any]:
        workflow_id = str(uuid.uuid4())
        query = request.query
        session_id = query.get("session_id") or query.get("query_id") or workflow_id

        state: AgentWorkflowState = {
            "workflow_id": workflow_id,
            "query": query,
            "context": request.context,
            "memory": request.memory or self._format_session_memory(session_id),
            "current_stage": "created",
            "intermediate_results": {},
            "tool_calls": [],
            "error_messages": [],
        }
        final_state = await self.orchestrator.execute(state)
        self.workflows[workflow_id] = final_state
        self._append_session_memory(session_id, query.get("query_text", ""), final_state.get("final_answer", ""))

        return {
            "workflow_id": workflow_id,
            "response": final_state.get("final_answer", ""),
            "thoughts": json.dumps(final_state.get("intermediate_results", {}), default=str),
            "agent_used": "langgraph_multi_agent",
            "confidence": 0.75 if final_state.get("final_answer") else 0.2,
            "processing_time": 0.0,
            "tool_calls": final_state.get("tool_calls", []),
            "current_stage": final_state.get("current_stage"),
        }

    async def execute_workflow(self, workflow_state: WorkflowState) -> WorkflowState:
        state = await self.orchestrator.execute(
            {
                "workflow_id": workflow_state.workflow_id,
                "query": workflow_state.query.model_dump(),
                "context": {
                    "context": "\n\n".join(
                        doc.content for doc in workflow_state.retrieved_documents
                    )
                },
                "memory": "",
                "intermediate_results": workflow_state.intermediate_results,
                "tool_calls": [],
                "error_messages": workflow_state.error_messages,
            }
        )
        workflow_state.current_stage = state.get("current_stage", "complete")
        workflow_state.final_answer = state.get("final_answer")
        workflow_state.intermediate_results = state.get("intermediate_results", {})
        workflow_state.token_count = state.get("token_count", 0)
        return workflow_state

    async def call_tool(self, request: ToolCallRequest) -> Dict[str, Any]:
        result = await self.tool_registry.execute_tool(request.tool_name, **request.arguments)
        return {"tool_name": request.tool_name, "result": result}

    async def call_mcp_tool(self, provider_id: str, request: ToolCallRequest) -> Dict[str, Any]:
        result = await self.mcp_handler.call_tool(
            provider_id,
            request.tool_name,
            **request.arguments,
        )
        return {"provider_id": provider_id, "tool_name": request.tool_name, "result": result}

    def _format_session_memory(self, session_id: str) -> str:
        turns = self.session_memory.get(session_id, [])[-5:]
        return "\n".join(f"User: {turn['user']}\nAssistant: {turn['assistant']}" for turn in turns)

    def _append_session_memory(self, session_id: str, user: str, assistant: str) -> None:
        self.session_memory.setdefault(session_id, []).append(
            {"user": user, "assistant": assistant, "timestamp": datetime.utcnow().isoformat()}
        )


service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    service = AgentOrchestrationService()
    await service.initialize()
    yield
    await service.close()


app = FastAPI(
    title="Agent Orchestration Service",
    description="LangGraph workflows with tool calling, MCP-style tools, CrewAI and AutoGen learning specs",
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/orchestrate")
async def orchestrate(request: OrchestrationRequest):
    try:
        return await service.orchestrate(request)
    except Exception as e:
        logger.error(f"Orchestration failed: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@app.post("/execute-workflow")
async def execute_workflow(workflow_state: WorkflowState):
    result = await service.execute_workflow(workflow_state)
    return {
        "status": "success",
        "workflow_id": result.workflow_id,
        "final_answer": result.final_answer,
        "token_count": result.token_count,
    }


@app.post("/workflows")
async def create_workflow(query: Query):
    workflow_id = await service.create_workflow(query)
    return {"status": "created", "workflow_id": workflow_id}


@app.get("/workflows/{workflow_id}")
async def get_workflow_state(workflow_id: str):
    try:
        return {"status": "success", **await service.get_workflow_state(workflow_id)}
    except AgentOrchestrationError as e:
        raise HTTPException(status_code=404, detail=e.to_dict())


@app.post("/workflows/{workflow_id}/stages/{stage}")
async def execute_workflow_stage(workflow_id: str, stage: str):
    return await service.execute_workflow_stage(workflow_id, stage)


@app.get("/tools")
async def list_tools():
    tools = list(service.tool_registry.tools.values())
    return {
        "total": len(tools),
        "tools": [tool.to_dict() for tool in tools],
        "openai_tool_schema": service.tool_registry.as_openai_tools(),
    }


@app.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    return await service.call_tool(request)


@app.get("/mcp/providers/{provider_id}/tools")
async def list_mcp_tools(provider_id: str):
    provider = service.mcp_handler.providers.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "Provider not found"})
    return {"provider_id": provider_id, "tools": provider.list_tools()}


@app.post("/mcp/providers/{provider_id}/tools/call")
async def call_mcp_tool(provider_id: str, request: ToolCallRequest):
    return await service.call_mcp_tool(provider_id, request)


@app.get("/learning/crewai-roles")
async def crewai_roles():
    return service.role_catalog.crewai_specs()


@app.get("/learning/autogen-specs")
async def autogen_specs():
    return service.role_catalog.autogen_specs()


@app.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"agent_id": "retriever-1", "role": "retriever"},
            {"agent_id": "analyzer-1", "role": "analyzer"},
            {"agent_id": "executor-1", "role": "executor"},
            {"agent_id": "synthesizer-1", "role": "synthesizer"},
        ]
    }


@app.get("/health")
async def health_check():
    return await service.check_health()


@app.get("/ready")
async def readiness():
    return await service.readiness_probe()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
