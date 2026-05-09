"""
Comprehensive exception hierarchy for Agentic RAG Platform
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for the platform"""
    # Document ingestion errors
    INVALID_S3_EVENT = "INVALID_S3_EVENT"
    S3_ACCESS_ERROR = "S3_ACCESS_ERROR"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    
    # Document parsing errors
    PARSE_FAILED = "PARSE_FAILED"
    OCR_FAILED = "OCR_FAILED"
    CHUNK_ERROR = "CHUNK_ERROR"
    METADATA_EXTRACTION_FAILED = "METADATA_EXTRACTION_FAILED"
    
    # Duplicate detection errors
    HASH_COMPUTATION_FAILED = "HASH_COMPUTATION_FAILED"
    DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
    
    # Embedding errors
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    EMBEDDING_API_ERROR = "EMBEDDING_API_ERROR"
    
    # Query processing errors
    QUERY_ROUTING_FAILED = "QUERY_ROUTING_FAILED"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    LLM_API_ERROR = "LLM_API_ERROR"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    
    # Agent orchestration errors
    AGENT_INITIALIZATION_FAILED = "AGENT_INITIALIZATION_FAILED"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    TOOL_REGISTRY_ERROR = "TOOL_REGISTRY_ERROR"
    MCP_PROTOCOL_ERROR = "MCP_PROTOCOL_ERROR"
    
    # Database errors
    DB_OPERATION_FAILED = "DB_OPERATION_FAILED"
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    
    # Cache errors
    CACHE_ERROR = "CACHE_ERROR"
    CACHE_MISS = "CACHE_MISS"
    
    # General errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RAGException(Exception):
    """Base exception for all Agentic RAG errors"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        detail_str = f" Details: {self.details}" if self.details else ""
        return f"[{self.error_code.value}] {self.message}{detail_str}"


class DocumentIngestionError(RAGException):
    """Errors during document ingestion"""
    pass


class DocumentParsingError(RAGException):
    """Errors during document parsing"""
    pass


class DocumentDuplicationError(RAGException):
    """Errors in duplicate detection"""
    pass


class EmbeddingError(RAGException):
    """Errors during embedding generation"""
    pass


class QueryProcessingError(RAGException):
    """Errors during query processing"""
    pass


class ToolExecutionError(RAGException):
    """Errors during tool execution"""
    pass


class AgentOrchestrationError(RAGException):
    """Errors in agent orchestration"""
    pass


class DatabaseError(RAGException):
    """Database operation errors"""
    pass


class CacheError(RAGException):
    """Cache operation errors"""
    pass


class ValidationError(RAGException):
    """Validation errors"""
    pass


class TimeoutError(RAGException):
    """Operation timeout errors"""
    pass


class DependencyError(RAGException):
    """External dependency unavailable"""
    pass


# Mapping for HTTP status codes
ERROR_CODE_TO_HTTP_STATUS = {
    ErrorCode.INVALID_S3_EVENT: 400,
    ErrorCode.S3_ACCESS_ERROR: 503,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 400,
    ErrorCode.PARSE_FAILED: 422,
    ErrorCode.OCR_FAILED: 422,
    ErrorCode.CHUNK_ERROR: 422,
    ErrorCode.METADATA_EXTRACTION_FAILED: 422,
    ErrorCode.HASH_COMPUTATION_FAILED: 500,
    ErrorCode.DUPLICATE_DETECTED: 409,
    ErrorCode.EMBEDDING_FAILED: 503,
    ErrorCode.EMBEDDING_API_ERROR: 503,
    ErrorCode.QUERY_ROUTING_FAILED: 500,
    ErrorCode.TOOL_EXECUTION_FAILED: 500,
    ErrorCode.LLM_API_ERROR: 503,
    ErrorCode.RETRIEVAL_FAILED: 503,
    ErrorCode.AGENT_INITIALIZATION_FAILED: 500,
    ErrorCode.AGENT_EXECUTION_FAILED: 500,
    ErrorCode.TOOL_REGISTRY_ERROR: 500,
    ErrorCode.MCP_PROTOCOL_ERROR: 500,
    ErrorCode.DB_OPERATION_FAILED: 500,
    ErrorCode.DB_CONNECTION_ERROR: 503,
    ErrorCode.CACHE_ERROR: 503,
    ErrorCode.CACHE_MISS: 404,
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.TIMEOUT_ERROR: 504,
    ErrorCode.DEPENDENCY_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}
