"""
Pydantic schemas for Agentic RAG Platform
"""

from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    INGESTED = "ingested"
    PARSING = "parsing"
    PARSED = "parsed"
    EMBEDDING = "embedding"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentType(str, Enum):
    """Document type"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    TXT = "txt"
    IMAGE = "image"


class AgentRole(str, Enum):
    """Agent roles in the system"""
    RETRIEVER = "retriever"
    ANALYZER = "analyzer"
    SYNTHESIZER = "synthesizer"
    EXECUTOR = "executor"
    EVALUATOR = "evaluator"


class Document(BaseModel):
    """Document schema"""
    document_id: str = Field(..., description="Unique document ID")
    file_name: str = Field(..., description="Original file name")
    document_type: DocumentType = Field(..., description="Document type")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, description="Processing status")
    content: str = Field(default="", description="Extracted text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    chunks: List[str] = Field(default_factory=list, description="Text chunks")
    embeddings: List[List[float]] = Field(default_factory=list, description="Embeddings for chunks")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    version: int = Field(default=1, description="Document version")
    source_s3_path: Optional[str] = Field(default=None, description="S3 source path")
    
    class Config:
        use_enum_values = True


class Query(BaseModel):
    """Query schema"""
    query_id: str = Field(..., description="Unique query ID")
    query_text: str = Field(..., description="Query text")
    user_id: Optional[str] = Field(default=None, description="User ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Query filters")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Query metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    
    class Config:
        use_enum_values = True


class RetrievedDocument(BaseModel):
    """Retrieved document result"""
    document_id: str = Field(..., description="Document ID")
    file_name: str = Field(..., description="File name")
    chunk_index: int = Field(..., description="Chunk index")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Retrieval score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")


class QueryResult(BaseModel):
    """Query result schema"""
    query_id: str = Field(..., description="Query ID")
    answer: str = Field(..., description="Generated answer")
    retrieved_documents: List[RetrievedDocument] = Field(default_factory=list, description="Retrieved docs")
    agent_thoughts: Optional[str] = Field(default=None, description="Agent reasoning")
    confidence_score: float = Field(default=0.0, description="Confidence score")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Token usage stats")
    processing_time_ms: float = Field(default=0.0, description="Processing time in ms")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    
    class Config:
        use_enum_values = True


class AgentState(BaseModel):
    """Agent state schema"""
    agent_id: str = Field(..., description="Agent ID")
    agent_role: AgentRole = Field(..., description="Agent role")
    status: Literal["active", "idle", "paused", "error"] = Field(default="idle", description="Status")
    current_task: Optional[str] = Field(default=None, description="Current task")
    memory: Dict[str, Any] = Field(default_factory=dict, description="Agent memory")
    tools_available: List[str] = Field(default_factory=list, description="Available tools")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update")
    
    class Config:
        use_enum_values = True


class WorkflowState(BaseModel):
    """Workflow state for multi-agent orchestration"""
    workflow_id: str = Field(..., description="Workflow ID")
    query: Query = Field(..., description="Input query")
    retrieved_documents: List[RetrievedDocument] = Field(default_factory=list, description="Retrieved docs")
    agent_states: Dict[str, AgentState] = Field(default_factory=dict, description="Agent states")
    current_stage: str = Field(default="initialization", description="Current processing stage")
    intermediate_results: Dict[str, Any] = Field(default_factory=dict, description="Intermediate results")
    final_answer: Optional[str] = Field(default=None, description="Final answer")
    error_messages: List[str] = Field(default_factory=list, description="Error messages")
    token_count: int = Field(default=0, description="Total tokens used")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    class Config:
        use_enum_values = True


class EvaluationMetric(BaseModel):
    """Evaluation metric schema"""
    metric_name: str = Field(..., description="Metric name")
    score: float = Field(..., description="Metric score")
    details: Dict[str, Any] = Field(default_factory=dict, description="Metric details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")


class QueryEvaluation(BaseModel):
    """Query evaluation schema"""
    query_id: str = Field(..., description="Query ID")
    metrics: List[EvaluationMetric] = Field(default_factory=list, description="Evaluation metrics")
    feedback: Optional[str] = Field(default=None, description="User feedback")
    rating: Optional[int] = Field(default=None, ge=1, le=5, description="User rating 1-5")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    
    class Config:
        use_enum_values = True
