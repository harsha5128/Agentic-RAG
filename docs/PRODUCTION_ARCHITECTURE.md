# Agentic RAG Production Architecture Guide

## Overview

This document outlines the production-grade microservices architecture for the Agentic RAG system. Each service follows enterprise patterns for reliability, scalability, and maintainability.

## Architecture Principles

1. **Event-Driven**: Services communicate via events (S3, SQS) for decoupling
2. **Modular**: Each service has a single responsibility with clear interfaces
3. **Async-First**: All I/O operations use async/await
4. **Observable**: Comprehensive logging, tracing, and health checks
5. **Resilient**: Error handling, retries, and graceful degradation
6. **Testable**: Dependency injection and clear boundaries

## Service Architecture

### Document Ingestion Service (Port 8001)
**Responsibility**: Convert S3 uploads into processing tasks

**Event Flow**:
```
S3 Upload → S3:ObjectCreated → SQS → Document Ingestion Service
                                      ↓
                                    Validate
                                    ↓
                                 Compute Hash
                                    ↓
                                Check Duplicate
                                    ↓
                                Store Metadata (MongoDB)
                                    ↓
                                Publish to Parsing Queue (SQS)
```

**Key Features**:
- No direct file uploads (S3 event-driven only)
- Content hash for deduplication detection
- Metadata extraction from S3 object metadata
- Status tracking in MongoDB
- Comprehensive error handling with retry logic

**Endpoints**:
- `POST /ingest` - Process S3 event
- `GET /health` - Service health
- `GET /ready` - Readiness probe
- `GET /live` - Liveness probe

### Document Parsing Service (Port 8002)
**Responsibility**: Parse documents into structured content and chunks

**Architecture**:
```
DocumentParser (Abstract)
├── PDFParser (with OCR support)
├── DOCXParser (with table extraction)
├── SpreadsheetParser (XLSX/CSV)
├── ImageParser (with pytesseract)
└── TextParser (UTF-8/Latin-1)

DocumentChunker
└── Semantic paragraph-based chunking

DocumentParsingService (BaseService)
├── Dependency management
├── MongoDB persistence
└── Status tracking
```

**Parsing Features**:
- Format-specific handlers for each document type
- Metadata extraction (title, author, pages, tables, etc.)
- OCR support for image-based PDFs
- Semantic chunking with paragraph awareness
- Content hash for duplicate detection
- Error recovery with detailed logging

**Processing Pipeline**:
```
S3 Download
    ↓
Format Detection
    ↓
Parser Selection
    ↓
Parse & Extract Metadata
    ↓
Semantic Chunking
    ↓
Store Parsed Content (MongoDB)
    ↓
Update Document Status
    ↓
Ready for Embedding
```

### Agent Orchestration Service (Port 8003)
**Responsibility**: Manage agent workflows, function tools, and MCP protocol

**Components**:

1. **AgentToolRegistry**
   - Register and manage executable tools
   - Enforce role-based access control
   - Execute tools with error handling

2. **Agent**
   - Represents an agent with a specific role
   - Maintains local state and memory
   - Available tools based on role

3. **WorkflowOrchestrator**
   - Multi-stage workflow execution
   - Agent coordination
   - Workflow state management

4. **MCPProtocolHandler**
   - Model Context Protocol integration
   - Provider management
   - Tool execution through MCP

**Workflow Stages**:
```
Initialization
    ↓
Retrieval Stage (Retriever Agent)
    ↓
Reasoning Stage (Analyzer Agent)
    ↓
Tool Use Stage (Executor Agent)
    ↓
Synthesis Stage (Synthesizer Agent)
    ↓
Evaluation Stage (Evaluator Agent)
```

**Agent Roles**:
- `RETRIEVER`: Finds relevant documents
- `ANALYZER`: Analyzes and understands information
- `SYNTHESIZER`: Generates responses
- `EXECUTOR`: Executes tools and functions
- `EVALUATOR`: Evaluates response quality

### Query Processing Service (TODO)
**Responsibility**: Advanced query resolution with agentic workflows

**Features** (To Implement):
- Complex query routing and decomposition
- Multi-step reasoning with function calling
- Integration with Agent Orchestration Service
- State machine for query workflows
- Retrieval augmented generation (RAG)
- Feedback loops for continuous improvement
- Query result caching

**Expected Flow**:
```
User Query
    ↓
Query Analysis
    ↓
Function Calling Decision
    ↓
Retrieval Query Preparation
    ↓
Retrieve Documents
    ↓
Analyze Retrieved Context
    ↓
Determine Tools Needed
    ↓
Execute Tools via MCP/Executor
    ↓
Synthesize Final Response
    ↓
Evaluate Response Quality
    ↓
Cache Result
```

## Core Patterns & Best Practices

### 1. Service Base Class

All services inherit from `BaseService`:

```python
class DocumentParsingService(BaseService):
    def __init__(self):
        super().__init__("document-parsing-service")
        # Service setup
    
    async def _initialize_dependencies(self):
        # Register health checks
        self.register_dependency("mongodb", self._check_mongodb_health)
```

**Provides**:
- Automatic client initialization (S3, SQS, MongoDB, Redis)
- Health check framework
- Error handling with tracing
- Cache operations
- Database session management
- Lifecycle management

### 2. Error Handling

**Custom Exception Hierarchy**:
```python
RAGException (base)
├── DocumentIngestionError
├── DocumentParsingError
├── EmbeddingError
├── QueryProcessingError
├── AgentOrchestrationError
├── ToolExecutionError
└── ... (20+ specific errors)
```

**Error Codes**:
- Specific error codes for each failure type
- Automatic HTTP status code mapping
- Serializable error responses
- Original error tracking for debugging

### 3. Database Models

**MongoDB Collections**:
- `documents`: Main document records with TTL
- `parsed_contents`: Parsed and chunked content
- `workflow_states`: Active workflow states (24hr TTL)
- `evaluation_metrics`: Query evaluation results
- `agent_tool_registry`: Available tools per agent
- `query_cache`: Cached query results (7-day TTL)

**Patterns**:
- Automatic index creation on service startup
- Type-safe query helpers
- TTL indexes for automatic cleanup
- Efficient composite indexes

### 4. Health Checks

**Three-Tier Health System**:

1. **Service Health** (`/health`):
   ```json
   {
     "service": "document-parsing-service",
     "healthy": true,
     "dependencies": {
       "s3": {"healthy": true},
       "mongodb": {"healthy": true}
     }
   }
   ```

2. **Readiness Probe** (`/ready`):
   - Returns 200 only when service can accept requests
   - Checks all critical dependencies
   - Used by Kubernetes for traffic routing

3. **Liveness Probe** (`/live`):
   - Simple check that service process is running
   - Used by Kubernetes for restart decisions

### 5. Async Patterns

**All Operations Are Async**:
```python
async def parse_document(self, s3_path: str) -> Dict:
    return await self.with_error_handling(
        self._parse_document_impl,
        "parse_document",
        s3_path,
    )
```

**Benefits**:
- Non-blocking I/O
- Better resource utilization
- Natural concurrency handling
- Scalable under load

### 6. Observability

**Logging**:
- Structured logging with loguru
- Correlation IDs for request tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Tracing**:
- OpenTelemetry integration
- Jaeger exporter for distributed tracing
- Automatic span creation for operations
- Custom span attributes

**Metrics**:
- Request counts
- Error rates
- Latency tracking
- Service health metrics

## Data Models

### Document State Machine

```
PENDING → INGESTED → PARSING → PARSED → EMBEDDING → EMBEDDED → INDEXED
           ↓           ↓        ↓         ↓         ↓
         FAILED      FAILED   FAILED    FAILED    FAILED
```

### Workflow State Machine

```
initialization → retrieval → reasoning → tool_use → synthesis → evaluation
                    ↓            ↓         ↓         ↓          ↓
                  error        error     error     error      error
```

## Configuration

### Environment Variables

**AWS**:
```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/xxx/parsing-queue
S3_BUCKET_NAME=rag-documents
```

**Database**:
```
MONGODB_URI=mongodb://admin:pass@localhost:27017/rag_db
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=xxx
```

**LLM**:
```
OPENAI_API_KEY=sk-xxx
LLM_MODEL_NAME=gpt-4
TEMPERATURE=0.7
```

**Document Processing**:
```
CHUNK_SIZE=1024
CHUNK_OVERLAP=128
OCR_ENABLED=true
MAX_FILE_SIZE_MB=100
```

## Deployment

### Docker Deployment

Each service has a `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: document-parsing-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: parsing
        image: rag-document-parsing:latest
        readinessProbe:
          httpGet:
            path: /ready
            port: 8002
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /live
            port: 8002
          initialDelaySeconds: 15
          periodSeconds: 10
```

### Docker Compose

```yaml
version: '3.8'
services:
  document-ingestion:
    build: ./services/document_ingestion
    ports:
      - "8001:8001"
    environment:
      - AWS_REGION=us-east-1
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo

  document-parsing:
    build: ./services/document_parsing
    ports:
      - "8002:8002"
    environment:
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo

  agent-orchestration:
    build: ./services/agent_orchestration
    ports:
      - "8003:8003"
    environment:
      - MONGODB_URI=mongodb://mongo:27017
    depends_on:
      - mongo

  mongo:
    image: mongo:6.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: changeme
```

## Performance Considerations

### Chunking Strategy
- Semantic paragraph-based chunking
- Configurable chunk size (default 1024 chars)
- Overlap between chunks (default 128 chars)
- Preserves document structure context

### Caching
- Query results cached in MongoDB (7 days)
- Redis session cache for workflow state
- Document metadata cache per service
- Distributed cache for multi-instance deployments

### Scalability
- Services can scale independently
- Event-driven decoupling via S3/SQS
- Async processing throughout
- Stateless service design
- Horizontal scaling with load balancing

## Testing Strategy

1. **Unit Tests**
   - Parser functionality
   - Chunking logic
   - Error handling

2. **Integration Tests**
   - S3 → SQS → Service flow
   - MongoDB operations
   - Service health checks

3. **End-to-End Tests**
   - Document from upload to retrieval
   - Query through Agent Orchestration
   - Evaluation metrics

4. **Load Tests**
   - Concurrent document processing
   - High query volume
   - Service scaling behavior

## Monitoring & Alerts

**Key Metrics**:
- Document ingestion rate
- Average parsing time
- Agent workflow completion rate
- Query latency (P50, P95, P99)
- Error rates by type
- Cache hit rate
- MongoDB query performance

**Alerts**:
- Service health check failures
- High error rate (>5%)
- Slow query performance (>5s)
- Queue depth increasing
- Cache miss rate high

## Future Enhancements

1. **Advanced Chunking**
   - ML-based semantic chunking
   - Cross-document relationship detection
   - Table-aware chunking

2. **Tool Management**
   - Dynamic tool registration
   - Tool chaining for complex tasks
   - Tool versioning

3. **Agent Intelligence**
   - Learning from feedback
   - Agent specialization
   - Dynamic tool selection

4. **Query Optimization**
   - Query caching with relevance
   - Prefetching strategies
   - Adaptive retrieval depth

5. **Evaluation**
   - RAGAS metrics
   - Custom evaluation pipelines
   - A/B testing framework
